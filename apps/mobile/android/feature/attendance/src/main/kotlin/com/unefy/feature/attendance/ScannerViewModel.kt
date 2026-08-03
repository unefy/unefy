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
import android.util.Log
import com.unefy.feature.attendance.nfc.CheckInApdu
import com.unefy.feature.attendance.nfc.NfcState
import com.unefy.core.network.ApiResult
import dagger.hilt.android.lifecycle.HiltViewModel
import java.time.Instant
import java.util.concurrent.Executors
import javax.inject.Inject
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

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

    /** Held on the device. Not lost, just not sent yet. */
    data class QueuedOffline(val memberLabel: String?) : ScanFeedback

    /**
     * A unefy phone was tapped, but it has never fetched a seed — so it has no
     * code to give. Distinct because the remedy is "open the app once", not
     * "ask for a fresh code".
     */
    data object CardNotReady : ScanFeedback

    /** Nothing to check into. Previously this silently swallowed the scan. */
    data object NoSessionChosen : ScanFeedback

    /** A second scan arrived while the first was still in flight. */
    data object Busy : ScanFeedback

    /** Antennas found each other. Hold still. */
    data object Detected : ScanFeedback

    /** A check-in was taken back. */
    data class Undone(val memberName: String) : ScanFeedback

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
    /** Free text for somebody who is not a member. */
    val guestName: String = "",
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
    /** Check-ins taken while offline and not yet sent. */
    val pending: Int = 0,
    /** Whether this device can currently read a phone. */
    val nfc: NfcState = NfcState.Idle,
    /** True while a session is being opened from here. */
    val creatingSession: Boolean = false,
    /** Who is in this session, newest first. Recorded and buffered together. */
    val attendance: List<CheckedInEntry> = emptyList(),
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
    private val queue: CheckInQueue,
    private val deviceIdentity: DeviceIdentity,
    private val clock: AttendanceClock,
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

        viewModelScope.launch {
            queue.pendingCount.collect { count -> _uiState.update { it.copy(pending = count) } }
        }
        // Opening the scanner is the moment a supervisor has both a reason to
        // care and, usually, a connection again.
        drainQueue()
    }

    /** Sends whatever was taken offline. Safe to call when there is nothing. */
    fun drainQueue() {
        viewModelScope.launch { queue.sync() }
    }

    fun loadSessions() {
        _uiState.update { it.copy(loadingSessions = true, sessionsError = null) }
        viewModelScope.launch {
            when (val result = repository.openSessions()) {
                is ApiResult.Success -> {
                    _uiState.update { state ->
                        state.copy(
                            sessions = result.data,
                            // Preselect when there is no choice to make — the
                            // common case is one training evening running now.
                            selectedSessionId = state.selectedSessionId
                                ?: result.data.singleOrNull()?.id,
                            loadingSessions = false,
                        )
                    }
                    refreshAttendance()
                }

                is ApiResult.Failure -> _uiState.update {
                    it.copy(loadingSessions = false, sessionsError = result.error)
                }
            }
        }
    }

    /**
     * Opens a session for right now.
     *
     * Without this a supervisor standing at the range with nothing open has no
     * way forward: the scanner shows an empty screen and the evening goes
     * unrecorded unless somebody finds a laptop. Deliberately without a form —
     * the one thing being asked is "start now", and a title and an end time can
     * be corrected afterwards in the web app, where there is a keyboard.
     */
    fun createSessionForToday(title: String) {
        if (_uiState.value.creatingSession) return
        _uiState.update { it.copy(creatingSession = true) }

        viewModelScope.launch {
            val now = clock.epochSeconds()
            val result = repository.createSession(
                title = title,
                opensAt = Instant.ofEpochSecond(now).toString(),
                // Long enough for any training evening. Closing is what freezes
                // a session, and that stays a deliberate act — this is only the
                // window in which check-ins are accepted.
                closesAt = Instant.ofEpochSecond(now + SESSION_LENGTH_SECONDS).toString(),
            )
            _uiState.update { it.copy(creatingSession = false) }

            if (result is ApiResult.Success) {
                loadSessions()
                selectSession(result.data.id)
            } else if (result is ApiResult.Failure) {
                _uiState.update { it.copy(feedback = feedbackFor(result.error)) }
            }
        }
    }

    fun selectSession(sessionId: String) {
        // A new session means the same person may legitimately be scanned
        // again, so the seen-code memory starts over.
        handled.clear()
        _uiState.update {
            it.copy(
                selectedSessionId = sessionId,
                feedback = null,
                checkedInCount = 0,
                attendance = emptyList(),
            )
        }
        refreshAttendance()
    }

    suspend fun bindToCamera(context: Context, lifecycleOwner: LifecycleOwner) {
        val provider = ProcessCameraProvider.awaitInstance(context)

        // CameraX insists on the main thread for bind and unbind, and
        // awaitInstance resumes on whichever executor completed its future —
        // usually a background one. Calling straight through happened to work
        // by hand and threw "Not in application's main thread" under test.
        withContext(Dispatchers.Main.immediate) {
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
                // NonCancellable, or this would be skipped by the very
                // cancellation that is asking for the camera back.
                withContext(NonCancellable) { provider.unbindAll() }
            }
        }
    }

    /**
     * A code that arrived by NFC instead of through the camera.
     *
     * Same path deliberately — same duplicate guard, same queue, same feedback
     * — with one addition: the outcome is handed back over the still-open link
     * so the member's phone can say it too. That back-channel is the reason NFC
     * exists next to a QR that already worked.
     */
    fun onCodeTapped(code: String, respond: (CheckInApdu.Outcome) -> Unit) {
        // A tap is one deliberate act, not thirty camera frames of the same QR,
        // so the frame guard must not apply: tapping again after a rejection is
        // the obvious thing to try, and swallowing it looks like a dead app.
        onCodeScanned(code, deduplicate = false) { feedback ->
            Log.i(TAG, "tap outcome: $feedback")
            respond(
                when (feedback) {
                    is ScanFeedback.CheckedIn -> CheckInApdu.Outcome.RECORDED
                    is ScanFeedback.QueuedOffline -> CheckInApdu.Outcome.QUEUED
                    ScanFeedback.AlreadyPresent -> CheckInApdu.Outcome.ALREADY_PRESENT
                    else -> CheckInApdu.Outcome.REJECTED
                },
            )
        }
    }

    /**
     * Shows a refusal and tells the caller, so a tap always gets an answer.
     */
    private fun refuse(feedback: ScanFeedback, onResult: ((ScanFeedback) -> Unit)?) {
        _uiState.update { it.copy(feedback = feedback) }
        onResult?.invoke(feedback)
    }

    /**
     * Contact made, nothing decided yet.
     *
     * Its own state so the screen can say "hold still" the instant the
     * antennas find each other, which is the only cue that turns hunting for
     * the spot into holding a found one.
     */
    /**
     * Pulls everything this screen shows from the server again.
     *
     * Sessions first, because a session closed elsewhere has to disappear
     * before its attendance is fetched — otherwise the list reloads under a
     * chip that should no longer be there.
     */
    fun refresh() {
        loadSessions()
        drainQueue()
    }

    /**
     * Takes one check-in back.
     *
     * Both kinds, because from where the supervisor stands they are the same
     * mistake: a queued one is dropped outright, since it reached no server and
     * has no trail to keep consistent; a recorded one is soft-deleted and
     * audited. The server refuses the second once the session is closed, which
     * is the line this must not cross.
     */
    fun undo(entry: CheckedInEntry) {
        viewModelScope.launch {
            if (entry.pending) {
                entry.key.removePrefix("pending-").toLongOrNull()?.let { queue.discard(it) }
            } else {
                val result = repository.deleteRecord(entry.key)
                if (result is ApiResult.Failure) {
                    _uiState.update { it.copy(feedback = feedbackFor(result.error)) }
                    return@launch
                }
            }
            _uiState.update { it.copy(feedback = ScanFeedback.Undone(entry.memberName)) }
            refreshAttendance()
        }
    }

    fun onNfcState(state: NfcState) {
        _uiState.update { it.copy(nfc = state) }
    }

    fun onTagDetected() {
        _uiState.update { it.copy(feedback = ScanFeedback.Detected) }
    }

    /** A tap from a phone that has never fetched a seed. */
    fun onTapNotReady() {
        _uiState.update { it.copy(feedback = ScanFeedback.CardNotReady) }
    }

    /**
     * @param deduplicate suppresses repeats of the same code. Right for camera
     *   frames, wrong for a tap — see [onCodeTapped].
     */
    private fun onCodeScanned(
        code: String,
        deduplicate: Boolean = true,
        onResult: ((ScanFeedback) -> Unit)? = null,
    ) {
        val state = _uiState.value

        // These three used to return in silence, which is how a tap could
        // produce nothing at all: no message on the scanner and no reply to the
        // card, so both phones looked broken. A refusal is a result and has to
        // travel like one.
        val sessionId = state.selectedSessionId ?: return refuse(
            ScanFeedback.NoSessionChosen,
            onResult,
        )
        if (state.submitting) return refuse(ScanFeedback.Busy, onResult)
        if (deduplicate && !handled.add(code)) return

        _uiState.update { it.copy(submitting = true) }
        viewModelScope.launch {
            val result = queue.scan(sessionId, code, deviceIdentity.installId())
            var feedback: ScanFeedback? = null
            _uiState.update { current ->
                when (result) {
                    is CheckInResult.Recorded -> current.copy(
                        submitting = false,
                        feedback = ScanFeedback.CheckedIn(
                            result.outcome.memberName,
                            result.outcome.memberNumber,
                        ),
                    )

                    // Counted like any other: from where the supervisor stands
                    // the person is checked in, and the queue is the app's
                    // problem rather than theirs.
                    CheckInResult.Queued -> current.copy(
                        submitting = false,
                        feedback = ScanFeedback.QueuedOffline(memberLabel = null),
                    )

                    is CheckInResult.Rejected -> current.copy(
                        submitting = false,
                        feedback = feedbackFor(result.error),
                    )
                }.also { feedback = it.feedback }
            }
            feedback?.let { onResult?.invoke(it) }
            // The list is the confirmation, so it has to follow every scan.
            refreshAttendance()
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

            _uiState.update { state ->
                // The query may have moved on while these were in flight.
                if (state.manual.query != query) return@update state
                state.copy(
                    manual = when (members) {
                        is ApiResult.Failure ->
                            state.manual.copy(loading = false, error = members.error)

                        is ApiResult.Success ->
                            state.manual.copy(loading = false, members = members.data)
                    },
                )
            }
        }
        refreshAttendance()
    }

    /**
     * Reloads who is in the session, and merges in what this device still
     * holds.
     *
     * Both together, always: a list that omitted the buffered ones would tell a
     * supervisor to fetch someone who is standing in front of them.
     */
    fun refreshAttendance() {
        val sessionId = _uiState.value.selectedSessionId ?: return
        viewModelScope.launch {
            val recorded = when (val result = repository.sessionRecords(sessionId)) {
                is ApiResult.Success -> result.data
                is ApiResult.Failure -> emptyList()
            }
            val queued = queue.pendingFor(sessionId).map { entry ->
                CheckedInEntry(
                    key = "pending-${entry.id}",
                    memberId = entry.memberId,
                    memberName = entry.memberLabel.orEmpty(),
                    method = if (entry.code != null) "staff_scan" else "manual",
                    checkedInAtEpochSeconds = entry.checkedInAtEpochSeconds,
                    pending = true,
                )
            }

            // Queued first only where it is genuinely newer; the merged list
            // stays in one order so nothing appears to jump.
            val merged = (recorded + queued).sortedByDescending { it.checkedInAtEpochSeconds }
            _uiState.update { state ->
                state.copy(
                    attendance = merged,
                    checkedInCount = merged.size,
                    // Only real member ids: a guest has none, and folding a
                    // null or a blank in here would tick an arbitrary row.
                    manual = state.manual.copy(
                        checkedIn = merged.mapNotNull { it.memberId }.toSet(),
                    ),
                )
            }
        }
    }

    fun checkInManually(member: MemberPick) {
        val sessionId = _uiState.value.selectedSessionId ?: return
        if (_uiState.value.manual.pending != null) return

        _uiState.update { it.copy(manual = it.manual.copy(pending = member.id)) }
        viewModelScope.launch {
            val result = queue.checkInManually(sessionId, member, deviceIdentity.installId())
            _uiState.update { state ->
                when (result) {
                    is CheckInResult.Recorded, CheckInResult.Queued -> state.copy(
                        feedback = if (result is CheckInResult.Queued) {
                            ScanFeedback.QueuedOffline(member.name)
                        } else {
                            ScanFeedback.CheckedIn(member.name, member.memberNumber)
                        },
                        manual = state.manual.copy(
                            pending = null,
                            // Marked straight away rather than after a reload:
                            // the supervisor is working down a queue and the row
                            // has to settle before they look at the next name.
                            // A queued one is marked too — it is taken, and
                            // offering the row again would produce a duplicate.
                            checkedIn = state.manual.checkedIn + member.id,
                        ),
                    )

                    is CheckInResult.Rejected -> state.copy(
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
            refreshAttendance()
        }
    }

    /**
     * A guest, entered by name.
     *
     * No duplicate check and no row to mark: the backend accepts two guests of
     * the same name on purpose, because nothing about a guest tells them apart.
     */
    fun checkInGuest(name: String) {
        val sessionId = _uiState.value.selectedSessionId ?: return
        val trimmed = name.trim()
        if (trimmed.isEmpty()) return

        viewModelScope.launch {
            val result = queue.checkInGuest(sessionId, trimmed, deviceIdentity.installId())
            _uiState.update { state ->
                state.copy(
                    feedback = when (result) {
                        is CheckInResult.Recorded -> ScanFeedback.CheckedIn(trimmed, null)
                        CheckInResult.Queued -> ScanFeedback.QueuedOffline(trimmed)
                        is CheckInResult.Rejected -> feedbackFor(result.error)
                    },
                    manual = state.manual.copy(guestName = ""),
                )
            }
            refreshAttendance()
        }
    }

    fun onGuestNameChange(name: String) {
        _uiState.update { it.copy(manual = it.manual.copy(guestName = name)) }
    }

    private fun isAlreadyPresent(error: ApiError) =
        error is ApiError.Http && error.code == ALREADY_CHECKED_IN

    override fun onCleared() {
        analysisUseCase.clearAnalyzer()
        analysisExecutor.shutdown()
        super.onCleared()
    }

    private companion object {
        const val TAG = "unefy.nfc.reader"
        const val UNPROCESSABLE = 422

        /** Eight hours — longer than any evening, and closing is explicit. */
        const val SESSION_LENGTH_SECONDS = 8 * 60 * 60L

        // Both are 409. The backend gives them distinct codes precisely so the
        // scanner can say "already here" instead of accusing someone of
        // reusing a code — see backend/app/services/attendance.py.
        const val ALREADY_CHECKED_IN = "ALREADY_CHECKED_IN"
        const val CODE_ALREADY_USED = "CODE_ALREADY_USED"
    }
}
