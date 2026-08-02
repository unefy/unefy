package com.unefy.feature.attendance

import android.content.Context
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.core.SurfaceRequest
import androidx.camera.lifecycle.ProcessCameraProvider
// An extension on the companion, not a member, so it needs its own import.
import androidx.camera.lifecycle.awaitInstance
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import dagger.hilt.android.lifecycle.HiltViewModel
import java.util.concurrent.Executors
import javax.inject.Inject
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** What the supervisor sees after each scan. One line, gone on the next code. */
sealed interface ScanFeedback {
    data class CheckedIn(val memberName: String?, val memberNumber: String?) : ScanFeedback

    /** Already in this session — routine, not an error worth alarming anyone. */
    data object AlreadyPresent : ScanFeedback

    data object CodeUsed : ScanFeedback

    data object CodeInvalid : ScanFeedback

    /**
     * No connection. Its own case because the consequence differs: the other
     * failures mean the check-in did not happen and should not, this one means
     * it did not happen but should have — and the supervisor has to note the
     * person down, because nothing queues it yet.
     */
    data object Offline : ScanFeedback

    data class Failed(val error: ApiError) : ScanFeedback
}

/**
 * The manual list: everyone who could be here, and who already is.
 *
 * Not an alternative to scanning but the other half of it. Someone always turns
 * up with a flat battery, and the paper list they replace could always be ticked
 * by hand — a scanner that cannot do that is a downgrade.
 */
data class ManualPickState(
    val open: Boolean = false,
    val query: String = "",
    val members: List<MemberPick> = emptyList(),
    val checkedIn: Set<String> = emptySet(),
    val loading: Boolean = false,
    val error: ApiError? = null,
    /** The member whose check-in is in flight, so their row can lock. */
    val pending: String? = null,
)

data class ScannerUiState(
    val sessions: List<AttendanceSessionSummary> = emptyList(),
    val selectedSessionId: String? = null,
    val loadingSessions: Boolean = true,
    val sessionsError: ApiError? = null,
    /** Non-null once the camera has a surface to draw on. */
    val surfaceRequest: SurfaceRequest? = null,
    val submitting: Boolean = false,
    val feedback: ScanFeedback? = null,
    val checkedInCount: Int = 0,
    val manual: ManualPickState = ManualPickState(),
)

/**
 * The supervisor's scanner: camera in, check-ins out.
 *
 * The camera use cases live here rather than in the composable because they
 * outlive recomposition and must be bound exactly once — rebinding on every
 * frame is how a scanner ends up flickering.
 */
@HiltViewModel
class ScannerViewModel @Inject constructor(
    private val repository: AttendanceRepository,
    private val deviceIdentity: DeviceIdentity,
) : ViewModel() {

    private val _uiState = MutableStateFlow(ScannerUiState())
    val uiState: StateFlow<ScannerUiState> = _uiState.asStateFlow()

    /** Codes already sent, so one QR held under the lens is not posted 30 times. */
    private val handled = mutableSetOf<String>()

    private val analysisExecutor = Executors.newSingleThreadExecutor()

    private val previewUseCase = Preview.Builder().build().apply {
        setSurfaceProvider { request -> _uiState.update { it.copy(surfaceRequest = request) } }
    }

    private val analysisUseCase = ImageAnalysis.Builder()
        // The newest frame is the only one worth reading. Queueing frames would
        // make the scanner lag further behind the longer it runs.
        .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
        .build()

    init {
        loadSessions()
        analysisUseCase.setAnalyzer(analysisExecutor, QrAnalyzer(::onCodeScanned))
    }

    fun loadSessions() {
        _uiState.update { it.copy(loadingSessions = true, sessionsError = null) }
        viewModelScope.launch {
            when (val result = repository.openSessions()) {
                is ApiResult.Success -> _uiState.update { state ->
                    state.copy(
                        sessions = result.data,
                        // Preselect when there is no choice to make — the common
                        // case is one training evening running right now.
                        selectedSessionId = state.selectedSessionId
                            ?: result.data.singleOrNull()?.id,
                        loadingSessions = false,
                    )
                }

                is ApiResult.Failure -> _uiState.update {
                    it.copy(loadingSessions = false, sessionsError = result.error)
                }
            }
        }
    }

    fun selectSession(sessionId: String) {
        // A new session means the same person may legitimately be scanned
        // again, so the seen-code memory starts over.
        handled.clear()
        _uiState.update { it.copy(selectedSessionId = sessionId, feedback = null, checkedInCount = 0) }
    }

    suspend fun bindToCamera(context: Context, lifecycleOwner: LifecycleOwner) {
        val provider = ProcessCameraProvider.awaitInstance(context)
        provider.bindToLifecycle(
            lifecycleOwner,
            CameraSelector.DEFAULT_BACK_CAMERA,
            previewUseCase,
            analysisUseCase,
        )
        try {
            // Holds the binding for as long as the composable is on screen;
            // cancellation is what releases the camera.
            awaitCancellation()
        } finally {
            provider.unbindAll()
        }
    }

    private fun onCodeScanned(code: String) {
        val state = _uiState.value
        val sessionId = state.selectedSessionId ?: return
        if (state.submitting) return
        // The analyzer fires per frame; without this the same QR would be sent
        // repeatedly and every attempt after the first would come back as a
        // used code, turning a good scan into an error on screen.
        if (!handled.add(code)) return

        _uiState.update { it.copy(submitting = true) }
        viewModelScope.launch {
            val result = repository.scan(
                sessionId = sessionId,
                code = code,
                installId = deviceIdentity.installId(),
                staffDeviceId = deviceIdentity.installId(),
            )
            _uiState.update { current ->
                when (result) {
                    is ApiResult.Success -> current.copy(
                        submitting = false,
                        feedback = ScanFeedback.CheckedIn(
                            result.data.memberName,
                            result.data.memberNumber,
                        ),
                        checkedInCount = current.checkedInCount + 1,
                    )

                    is ApiResult.Failure -> {
                        // Never reached the server, so the code is unspent and
                        // pointing the camera at it again must work.
                        if (result.error is ApiError.Network) handled.remove(code)
                        current.copy(submitting = false, feedback = feedbackFor(result.error))
                    }
                }
            }
        }
    }

    /**
     * A rejected code is allowed to be retried, so it leaves the seen set —
     * except when it was consumed, which is permanent.
     */
    private fun feedbackFor(error: ApiError): ScanFeedback = when {
        error is ApiError.Network -> ScanFeedback.Offline
        error !is ApiError.Http -> ScanFeedback.Failed(error)
        error.code == ALREADY_CHECKED_IN -> ScanFeedback.AlreadyPresent
        error.code == CODE_ALREADY_USED -> ScanFeedback.CodeUsed
        error.status == UNPROCESSABLE -> ScanFeedback.CodeInvalid
        else -> ScanFeedback.Failed(error)
    }

    // --- Manual check-in ---

    fun openManualPick() {
        _uiState.update { it.copy(manual = it.manual.copy(open = true)) }
        refreshManualPick()
    }

    fun closeManualPick() {
        _uiState.update { it.copy(manual = it.manual.copy(open = false, query = "")) }
    }

    fun onManualQueryChange(query: String) {
        _uiState.update { it.copy(manual = it.manual.copy(query = query)) }
        refreshManualPick()
    }

    /**
     * Reloads the list and who is already in it.
     *
     * Both, every time: the two are read together and shown together, and a
     * list that says someone is missing when they were just scanned would send
     * a supervisor to fetch them.
     */
    private fun refreshManualPick() {
        val sessionId = _uiState.value.selectedSessionId ?: return
        val query = _uiState.value.manual.query

        _uiState.update { it.copy(manual = it.manual.copy(loading = true, error = null)) }
        viewModelScope.launch {
            val members = repository.members(query.takeIf(String::isNotBlank))
            val present = repository.checkedInMemberIds(sessionId)

            _uiState.update { state ->
                // The query may have moved on while these were in flight.
                if (state.manual.query != query) return@update state
                state.copy(
                    manual = when {
                        members is ApiResult.Failure ->
                            state.manual.copy(loading = false, error = members.error)

                        else -> state.manual.copy(
                            loading = false,
                            members = (members as ApiResult.Success).data,
                            // A failed record load is not worth an error screen:
                            // the list still works, it just cannot mark anyone.
                            checkedIn = (present as? ApiResult.Success)?.data
                                ?: state.manual.checkedIn,
                        )
                    },
                )
            }
        }
    }

    fun checkInManually(member: MemberPick) {
        val sessionId = _uiState.value.selectedSessionId ?: return
        if (_uiState.value.manual.pending != null) return

        _uiState.update { it.copy(manual = it.manual.copy(pending = member.id)) }
        viewModelScope.launch {
            val result = repository.checkInManually(sessionId, member.id)
            _uiState.update { state ->
                when (result) {
                    is ApiResult.Success -> state.copy(
                        feedback = ScanFeedback.CheckedIn(member.name, member.memberNumber),
                        checkedInCount = state.checkedInCount + 1,
                        manual = state.manual.copy(
                            pending = null,
                            // Marked straight away rather than after a reload:
                            // the supervisor is working down a queue and the row
                            // has to settle before they look at the next name.
                            checkedIn = state.manual.checkedIn + member.id,
                        ),
                    )

                    is ApiResult.Failure -> state.copy(
                        feedback = feedbackFor(result.error),
                        manual = state.manual.copy(
                            pending = null,
                            // Already present is not a failure worth hiding: mark
                            // the row, because that is what the list is claiming.
                            checkedIn = if (isAlreadyPresent(result.error)) {
                                state.manual.checkedIn + member.id
                            } else {
                                state.manual.checkedIn
                            },
                        ),
                    )
                }
            }
        }
    }

    private fun isAlreadyPresent(error: ApiError) =
        error is ApiError.Http && error.code == ALREADY_CHECKED_IN

    override fun onCleared() {
        analysisUseCase.clearAnalyzer()
        analysisExecutor.shutdown()
        super.onCleared()
    }

    private companion object {
        const val UNPROCESSABLE = 422

        // Both are 409. The backend gives them distinct codes precisely so the
        // scanner can say "already here" instead of accusing someone of
        // reusing a code — see backend/app/services/attendance.py.
        const val ALREADY_CHECKED_IN = "ALREADY_CHECKED_IN"
        const val CODE_ALREADY_USED = "CODE_ALREADY_USED"
    }
}
