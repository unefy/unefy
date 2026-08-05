package com.unefy.feature.attendance

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.unefy.core.auth.ClubRepository
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import dagger.hilt.android.lifecycle.HiltViewModel
import java.time.Instant
import java.time.ZoneId
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** The aftermath line above the list. */
sealed interface RangeDaysNotice {
    /** The entry is in — and honestly marked as self-kept. */
    data object Created : RangeDaysNotice

    /** An entry a certificate references cannot quietly lose its basis. */
    data object Certified : RangeDaysNotice

    /** Two visits on one day are one §14 day — the server keeps one entry. */
    data object DayTaken : RangeDaysNotice

    data class Failed(val error: ApiError) : RangeDaysNotice
}

/** The create form, while it is open. Field values live in the composable. */
data class SelfEntryForm(
    /** ISO date, defaults to today — an entry is made right after the visit. */
    val occurredOn: String,
    val saving: Boolean = false,
)

data class MyRangeDaysUiState(
    /** Club evenings and self-kept entries, newest first. */
    val days: List<OwnRangeDay> = emptyList(),
    val loading: Boolean = true,
    /** Only when there is nothing to show. */
    val error: ApiError? = null,
    val notice: RangeDaysNotice? = null,
    val form: SelfEntryForm? = null,
    /**
     * Null while the club has no shooting module: the form then asks only for
     * day and place, and the §14 vocabulary stays out of a gymnastics club.
     */
    val shooting: ShootingState? = null,
)

/**
 * The member's own range history, with the pen in their hand.
 *
 * The club's evenings arrive here read-only — they are the board's records.
 * What the member owns is the external entry: a visit to some other range,
 * self-kept because nobody else was there to attest it, and marked as exactly
 * that all the way to the certificate.
 */
@HiltViewModel
class MyRangeDaysViewModel @Inject constructor(
    private val repository: AttendanceRepository,
    private val clubRepository: ClubRepository,
    private val shootingDetails: ShootingDetailRepository,
    private val clock: AttendanceClock,
) : ViewModel() {

    private val _uiState = MutableStateFlow(MyRangeDaysUiState())
    val uiState: StateFlow<MyRangeDaysUiState> = _uiState.asStateFlow()

    init {
        probeShootingModule()
        refresh()
    }

    /** Same probe as the scanner's: silent on failure, absent without the module. */
    private fun probeShootingModule() {
        viewModelScope.launch {
            val club = (clubRepository.current() as? ApiResult.Success)?.data ?: return@launch
            if (!club.modules.contains(SHOOTING_MODULE)) return@launch

            val disciplines = (shootingDetails.disciplines() as? ApiResult.Success)?.data.orEmpty()
            _uiState.update { it.copy(shooting = ShootingState(disciplines = disciplines)) }
        }
    }

    fun refresh() {
        viewModelScope.launch {
            when (val result = repository.myRangeDays()) {
                is ApiResult.Success -> _uiState.update {
                    it.copy(days = result.data, loading = false, error = null)
                }

                is ApiResult.Failure -> _uiState.update { state ->
                    if (state.days.isEmpty()) {
                        state.copy(loading = false, error = result.error)
                    } else {
                        state.copy(loading = false)
                    }
                }
            }
        }
    }

    fun openForm() {
        val today = Instant.ofEpochSecond(clock.epochSeconds())
            .atZone(ZoneId.systemDefault())
            .toLocalDate()
            .toString()
        _uiState.update { it.copy(form = SelfEntryForm(occurredOn = today), notice = null) }
    }

    fun dismissForm() {
        _uiState.update { it.copy(form = null) }
    }

    fun setFormDate(isoDate: String) {
        _uiState.update { state ->
            state.copy(form = state.form?.copy(occurredOn = isoDate))
        }
    }

    /**
     * Writes the entry, then its shooting detail when one was given.
     *
     * Two calls by design — the entry is the §14 day, the detail is the range
     * book line — and the first succeeding without the second still recorded
     * the day. The notice then says "failed" so the person knows the detail is
     * missing, but the list shows the day, because it exists.
     */
    fun save(
        location: String,
        clubDisciplineId: String?,
        weaponCategory: String?,
        roundsFired: Int?,
    ) {
        val form = _uiState.value.form ?: return
        if (form.saving) return
        val trimmed = location.trim()
        if (trimmed.isEmpty()) return
        _uiState.update { it.copy(form = it.form?.copy(saving = true)) }

        viewModelScope.launch {
            when (val created = repository.createSelfEntry(form.occurredOn, trimmed)) {
                is ApiResult.Success -> {
                    val hasDetail =
                        clubDisciplineId != null || weaponCategory != null || roundsFired != null
                    var notice: RangeDaysNotice = RangeDaysNotice.Created
                    if (hasDetail && _uiState.value.shooting != null) {
                        val detail = shootingDetails.save(
                            recordId = created.data.id,
                            clubDisciplineId = clubDisciplineId,
                            weaponCategory = weaponCategory,
                            roundsFired = roundsFired,
                        )
                        if (detail is ApiResult.Failure) {
                            notice = RangeDaysNotice.Failed(detail.error)
                        }
                    }
                    _uiState.update { it.copy(form = null, notice = notice) }
                    refresh()
                }

                is ApiResult.Failure -> _uiState.update { state ->
                    state.copy(
                        // The form stays open, holding what was typed — except
                        // for the one refusal that typing cannot fix.
                        form = if (isDayTaken(created.error)) {
                            null
                        } else {
                            state.form?.copy(saving = false)
                        },
                        notice = if (isDayTaken(created.error)) {
                            RangeDaysNotice.DayTaken
                        } else {
                            RangeDaysNotice.Failed(created.error)
                        },
                    )
                }
            }
        }
    }

    /** Only external entries — the swipe is not offered on club rows. */
    fun delete(day: OwnRangeDay) {
        if (day.origin != "external") return
        viewModelScope.launch {
            when (val result = repository.deleteSelfEntry(day.id)) {
                is ApiResult.Success -> refresh()

                is ApiResult.Failure -> {
                    _uiState.update {
                        it.copy(
                            notice = if (isCertified(result.error)) {
                                RangeDaysNotice.Certified
                            } else {
                                RangeDaysNotice.Failed(result.error)
                            },
                        )
                    }
                    // The swipe already moved the row; only a reload brings it
                    // back after a refused delete.
                    refresh()
                }
            }
        }
    }

    private fun isCertified(error: ApiError) =
        error is ApiError.Http && error.code == "RECORD_CERTIFIED"

    private fun isDayTaken(error: ApiError) =
        error is ApiError.Http && error.code == "SELF_ENTRY_EXISTS"

    private companion object {
        /** As `sports.modules` spells it — see `require_module` on the server. */
        const val SHOOTING_MODULE = "shooting"
    }
}
