package com.unefy.feature.attendance

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.unefy.core.auth.ClubRepository
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** What the range table can enter beside a check-in. */
data class ShootingState(
    val disciplines: List<ClubDiscipline> = emptyList(),
    /** By attendance record id, as the endpoint returns it. */
    val details: Map<String, ShootingDetail> = emptyMap(),
    /** The row whose sheet is open, if any. */
    val editing: CheckedInEntry? = null,
    val saving: Boolean = false,
)

/** One line of aftermath — an undo that worked, or an action that did not. */
sealed interface AttendanceListNotice {
    data class Undone(val memberName: String) : AttendanceListNotice

    data class UndoFailed(val error: ApiError) : AttendanceListNotice

    data class SaveFailed(val error: ApiError) : AttendanceListNotice
}

data class AttendanceListUiState(
    /** Who is in this session, newest first. Recorded and buffered together. */
    val entries: List<CheckedInEntry> = emptyList(),
    val loading: Boolean = true,
    /** Only set when there is nothing at all to show — see [refresh]. */
    val error: ApiError? = null,
    val notice: AttendanceListNotice? = null,
    /**
     * The shooting module's side of a row, absent for a club without it.
     *
     * Null means the club has no shooting sport, so there is nothing to enter and
     * no sheet to open — not that the fields are empty.
     */
    val shooting: ShootingState? = null,
)

/**
 * The attendance list of one session, as its own screen.
 *
 * It used to live under the scanner's viewfinder, but the two answer different
 * questions: the scanner answers "did that scan work", this answers "who is in
 * the room and what did they shoot". Once the shooting details joined each row,
 * the list stopped being scan feedback and became data entry — which deserves a
 * full screen, not the space left over under a camera.
 */
@HiltViewModel
class AttendanceListViewModel @Inject constructor(
    private val repository: AttendanceRepository,
    private val queue: CheckInQueue,
    private val clubRepository: ClubRepository,
    private val shootingDetails: ShootingDetailRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(AttendanceListUiState())
    val uiState: StateFlow<AttendanceListUiState> = _uiState.asStateFlow()

    private var sessionId: String? = null

    fun load(sessionId: String) {
        if (this.sessionId == sessionId) return
        this.sessionId = sessionId
        probeShootingModule()
        refresh()
    }

    /**
     * Whether this club shoots, asked once per screen.
     *
     * Silent on failure. A club that shoots and briefly has no connection loses
     * the extra column for this visit; guessing the other way would show a
     * supervisor fields their club has no use for, and an error message about a
     * module nobody asked for is worse than the missing column.
     */
    private fun probeShootingModule() {
        viewModelScope.launch {
            val club = (clubRepository.current() as? ApiResult.Success)?.data ?: return@launch
            if (!club.modules.contains(SHOOTING_MODULE)) return@launch

            val disciplines = (shootingDetails.disciplines() as? ApiResult.Success)?.data.orEmpty()
            _uiState.update { it.copy(shooting = ShootingState(disciplines = disciplines)) }
            // The first refresh ran before this answer arrived and skipped the
            // details; this is the one that fills them in.
            refresh()
        }
    }

    /**
     * Reloads who is in the session, and merges in what this device still holds.
     *
     * Both together, always: a list that omitted the buffered ones would tell a
     * supervisor to fetch someone who is standing in front of them.
     */
    fun refresh() {
        val sessionId = sessionId ?: return
        viewModelScope.launch {
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

            when (val result = repository.sessionRecords(sessionId)) {
                is ApiResult.Success -> {
                    // Queued first only where it is genuinely newer; the merged
                    // list stays in one order so nothing appears to jump.
                    val merged = (result.data + queued)
                        .sortedByDescending { it.checkedInAtEpochSeconds }
                    val details = detailsFor(sessionId)
                    _uiState.update { state ->
                        state.copy(
                            entries = merged,
                            loading = false,
                            error = null,
                            shooting = state.shooting?.copy(details = details),
                        )
                    }
                }

                is ApiResult.Failure -> _uiState.update { state ->
                    // Only a failure when there is nothing to show. Replacing a
                    // list the supervisor is working down with an error because
                    // one reload tripped would be the worse screen.
                    if (state.entries.isEmpty() && queued.isEmpty()) {
                        state.copy(loading = false, error = result.error)
                    } else {
                        state.copy(loading = false)
                    }
                }
            }
        }
    }

    private suspend fun detailsFor(sessionId: String): Map<String, ShootingDetail> {
        if (_uiState.value.shooting == null) return emptyMap()
        return when (val result = shootingDetails.forSession(sessionId)) {
            is ApiResult.Success -> result.data
            // A failed read costs the summaries on the rows, not the list: who
            // was there is the answer that matters.
            is ApiResult.Failure -> _uiState.value.shooting?.details.orEmpty()
        }
    }

    /**
     * Takes one check-in back.
     *
     * Both kinds, because from where the supervisor stands they are the same
     * mistake: a queued one is dropped outright, since it reached no server and
     * has no trail to keep consistent; a recorded one is soft-deleted and
     * audited. No reason is sent, which is why this only works inside an open
     * session — a correction to a closed evening is made in the web app, where
     * there is a field to explain it.
     */
    fun undo(entry: CheckedInEntry) {
        viewModelScope.launch {
            if (entry.pending) {
                entry.key.removePrefix("pending-").toLongOrNull()?.let { queue.discard(it) }
            } else {
                val result = repository.deleteRecord(entry.key)
                if (result is ApiResult.Failure) {
                    _uiState.update {
                        it.copy(notice = AttendanceListNotice.UndoFailed(result.error))
                    }
                    return@launch
                }
            }
            _uiState.update { it.copy(notice = AttendanceListNotice.Undone(entry.memberName)) }
            refresh()
        }
    }

    /** Opens the sheet for one row. Guests have no detail to enter — see [saveShootingDetail]. */
    fun editShootingDetail(entry: CheckedInEntry) {
        _uiState.update { it.copy(shooting = it.shooting?.copy(editing = entry)) }
    }

    fun dismissShootingDetail() {
        _uiState.update { it.copy(shooting = it.shooting?.copy(editing = null)) }
    }

    /**
     * Writes what somebody shot.
     *
     * Online only, and that is a decision rather than an omission: a check-in is
     * taken at the door and cannot wait for a connection, which is why there is a
     * queue behind it, while this is filled in afterwards at the range table. A
     * second write queue with its own conflict rules would cost more than it buys.
     */
    fun saveShootingDetail(
        clubDisciplineId: String?,
        weaponCategory: String?,
        roundsFired: Int?,
    ) {
        val editing = _uiState.value.shooting?.editing ?: return
        _uiState.update { it.copy(shooting = it.shooting?.copy(saving = true)) }

        viewModelScope.launch {
            val result = shootingDetails.save(
                recordId = editing.key,
                clubDisciplineId = clubDisciplineId,
                weaponCategory = weaponCategory,
                roundsFired = roundsFired,
            )
            when (result) {
                is ApiResult.Success -> {
                    _uiState.update { state ->
                        state.copy(
                            shooting = state.shooting?.copy(
                                // Straight from the answer rather than from what
                                // was typed: the server is what the range book
                                // will print.
                                details = state.shooting.details +
                                    (result.data.attendanceRecordId to result.data),
                                editing = null,
                                saving = false,
                            ),
                        )
                    }
                }

                is ApiResult.Failure -> {
                    _uiState.update { state ->
                        state.copy(
                            notice = AttendanceListNotice.SaveFailed(result.error),
                            // The sheet stays open, holding what was typed: a
                            // failed save that closes the form loses the entry.
                            shooting = state.shooting?.copy(saving = false),
                        )
                    }
                }
            }
        }
    }

    private companion object {
        /** As `sports.modules` spells it — see `require_module` on the server. */
        const val SHOOTING_MODULE = "shooting"
    }
}
