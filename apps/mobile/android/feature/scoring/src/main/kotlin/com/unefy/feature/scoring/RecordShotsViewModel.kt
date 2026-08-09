package com.unefy.feature.scoring

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.unefy.core.model.scoring.Calibers
import com.unefy.core.model.scoring.SOURCE_SCAN
import com.unefy.core.model.scoring.ShotSeriesDraft
import com.unefy.core.model.scoring.TargetGeometry
import com.unefy.core.model.scoring.TargetGeometrySeed
import com.unefy.core.network.ApiError
import dagger.hilt.android.lifecycle.HiltViewModel
import java.time.LocalDate
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter
import java.util.UUID
import javax.inject.Inject
import com.unefy.core.network.ApiResult
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

sealed interface RecordShotsUiState {
    data object Loading : RecordShotsUiState

    /**
     * Everything the recording screen needs, with the draft always scored.
     *
     * The draft carries its own geometry and caliber, so the running total on
     * screen is produced by the same engine that will score the series on save —
     * the number can never disagree with itself.
     */
    data class Content(
        val draft: ShotSeriesDraft,
        val targetTypes: List<TargetGeometry>,
        val member: MemberOption?,
        /** Empty when the caller may only record for themselves. */
        val selectableMembers: List<MemberOption>,
        val expectedShots: Int?,
        val discipline: String?,
        val sessionId: String?,
        val occurredOn: String,
        /** A rectified photo of the real sheet, drawn under the rings. */
        val photo: android.graphics.Bitmap? = null,
        /**
         * True when the shooter has no attendance record for this day.
         *
         * A hint, never a gate: a result is not a proof of presence, and the
         * series saves either way. Only set for one's own series — nobody may
         * read anybody else's attendance.
         */
        val missingAttendance: Boolean = false,
        val saving: Boolean = false,
        val savedPending: Boolean = false,
        val error: ApiError? = null,
    ) : RecordShotsUiState {
        val canSave: Boolean get() = member != null && draft.shots.isNotEmpty() && !saving

        /** True when the count differs from what the discipline expects. */
        val shotCountMismatch: Boolean
            get() = expectedShots != null && draft.shots.size != expectedShots
    }

    data class Failure(val error: ApiError) : RecordShotsUiState
}

/**
 * Recording one series of shots.
 *
 * Two paths in, and they differ only in what is already known: from a
 * competition session the session id and discipline are fixed, and from the
 * member's own screen neither is — that case files under the club's automatic
 * free-training series, which the server creates on demand.
 */
@HiltViewModel
class RecordShotsViewModel @Inject constructor(
    private val repository: ScoringRepository,
    private val scans: SeriesScans,
) : ViewModel() {

    private val _uiState = MutableStateFlow<RecordShotsUiState>(RecordShotsUiState.Loading)
    val uiState: StateFlow<RecordShotsUiState> = _uiState.asStateFlow()

    private var initialised = false
    private var seriesId: String? = null

    /**
     * @param canPickMember board and above record for anyone; a plain member
     *   only for themselves, which the server enforces regardless.
     */
    fun start(
        sessionId: String?,
        discipline: String?,
        memberId: String?,
        canPickMember: Boolean,
        expectedShots: Int?,
        /** Set to correct a series that is already recorded. */
        seriesId: String? = null,
    ) {
        this.seriesId = seriesId
        // Guarded because a recomposition must not reset a half-entered series.
        if (initialised) return
        initialised = true

        // Render immediately from the built-in catalog. Waiting on the network
        // before showing anything was wrong on its own terms: the seed exists so
        // that a range with no signal still works, and a screen stuck on
        // "loading target" is exactly the failure it was meant to prevent. A
        // slow or unreachable server now costs nothing but a later refresh.
        val seed = TargetGeometrySeed.DEFAULT
        _uiState.value = RecordShotsUiState.Content(
            draft = ShotSeriesDraft(geometry = seed, caliberMm = seed.defaultCaliberMm),
            targetTypes = TargetGeometrySeed.ALL,
            member = memberId?.let { MemberOption(it, "") },
            selectableMembers = emptyList(),
            expectedShots = expectedShots,
            discipline = discipline,
            sessionId = sessionId,
            occurredOn = LocalDate.now().toString(),
        )

        viewModelScope.launch {
            // Correcting: the series being edited seeds the draft, so the shots
            // on screen are the ones that were recorded rather than an empty
            // sheet. Its photograph comes back too — a correction usually starts
            // with looking at the sheet again.
            // Both sources: the board corrects series it did not shoot, and
            // those live in the club mirror. Reading only the own history left
            // the sheet empty and the shooter unset — and saving that would have
            // written the blank draft over somebody else's series.
            val existing = seriesId?.let { id ->
                findSeries(id, repository.myHistory().first(), repository.clubHistory().first())
            }
            if (existing != null) {
                update { content ->
                    content.copy(
                        draft = ShotSeriesDraft(
                            geometry = existing.geometry ?: content.draft.geometry,
                            caliberMm = existing.caliberMm ?: content.draft.caliberMm,
                            shots = existing.shots,
                        ).rescored(),
                        photo = scans.load(existing.id, ScanStore.Kind.RECTIFIED),
                        occurredOn = existing.recordedAt.take(10),
                    )
                }
            }

            val members = if (canPickMember) repository.selectableMembers() else emptyList()
            val member = when {
                memberId != null -> members.firstOrNull { it.id == memberId }
                    ?: MemberOption(memberId, "")
                // Correcting: the series already names who shot it, so say so
                // rather than asking again. Preferring the entry from the member
                // list gets the current spelling of the name; the series' own
                // copy carries it on a device whose mirror has not synced.
                existing != null -> members.firstOrNull { it.id == existing.memberId }
                    ?: MemberOption(existing.memberId, existing.memberLabel ?: "")
                // Board picks from the list — but only if there is one. The
                // member mirror is filled by delta-sync, so on a device that has
                // not synced yet it is empty, and without this fallback the save
                // button would be permanently disabled with no way to explain
                // why. Falling back to the caller's own record at least lets
                // them record their own series.
                canPickMember && members.isNotEmpty() -> null
                else -> repository.ownMember()
            }
            update { it.copy(member = member, selectableMembers = members) }

            // Only for one's own series, and only when the answer is certain:
            // a member may not read anybody else's attendance, and a hint that
            // might be wrong is worse than none. Correcting an old series says
            // nothing about today, so it is skipped there too.
            if (seriesId == null && !canPickMember) {
                val day = (_uiState.value as? RecordShotsUiState.Content)?.occurredOn
                if (day != null && repository.hasAttendanceOn(day) == false) {
                    update { it.copy(missingAttendance = true) }
                }
            }
        }

        // The server catalog can correct a ring diameter without an app update,
        // so it still gets fetched — just not in front of the user.
        viewModelScope.launch {
            val targets = repository.targetTypes()
            if (targets.isEmpty()) return@launch
            update { content ->
                val current = targets.firstOrNull { it.slug == content.draft.geometry.slug }
                content.copy(
                    targetTypes = targets,
                    // Only swap the live geometry if the server's copy differs;
                    // rescoring mid-entry would move shots the user just placed.
                    draft = if (current != null && current != content.draft.geometry) {
                        content.draft.copy(geometry = current).rescored()
                    } else {
                        content.draft
                    },
                )
            }
        }
    }

    // --- Editing ---

    fun onDraftChange(draft: ShotSeriesDraft) = update { it.copy(draft = draft) }

    fun onMemberSelected(member: MemberOption) = update { it.copy(member = member) }

    /**
     * Switching the target rescores every shot already placed: the positions are
     * normalised, so they survive, but the ring table under them changed.
     */
    fun onTargetSelected(geometry: TargetGeometry) = update { content ->
        content.copy(
            draft = content.draft
                .copy(geometry = geometry, caliberMm = geometry.defaultCaliberMm)
                .rescored(),
        )
    }

    /** Same reasoning — a different caliber moves every ring boundary. */
    fun onCaliberSelected(caliberMm: Double) = update { content ->
        content.copy(draft = content.draft.copy(caliberMm = caliberMm).rescored())
    }

    fun onClearShots() = update { it.copy(draft = it.draft.copy(shots = emptyList())) }

    /**
     * Put a photographed, rectified target under the digital one, and place the
     * holes that were found in it.
     *
     * Shots already placed are kept and nothing is placed on top of them: the
     * coordinates are normalised to the scoring radius and the photo uses that
     * same frame, so a series half entered by hand still points where the
     * shooter put it, and having it silently doubled by the detector would be
     * worse than detecting nothing.
     *
     * What is placed is a proposal. A photograph cannot say which holes belong
     * to this series — the sheet carries every unpatched shot ever fired at it,
     * and it may carry a second shooter's series in another caliber
     * (ml/NOTES-real-targets.md §1, §1b). The shooter drags, adds and removes
     * from here; that is the point of placing them rather than counting them.
     */
    fun onPhotoCaptured(photo: TargetPhoto) = update { content ->
        val draft = if (content.draft.shots.isEmpty()) {
            photo.hits.fold(content.draft) { draft, hit ->
                draft.place(newShotId(), hit.x, hit.y, source = SOURCE_SCAN)
            }
        } else {
            content.draft
        }
        content.copy(photo = photo.rectified, draft = draft)
    }

    fun onPhotoDiscarded() = update { it.copy(photo = null) }

    fun onDismissError() = update { it.copy(error = null) }

    // --- Saving ---

    fun save(onSaved: (pending: Boolean) -> Unit) {
        val content = _uiState.value as? RecordShotsUiState.Content ?: return
        val member = content.member ?: return
        if (!content.canSave) return

        _uiState.value = content.copy(saving = true, error = null)
        viewModelScope.launch {
            // Correcting rewrites the series that was opened; only recording
            // fresh creates one. Without this branch the screen saved *every*
            // edit as a new series and left the original standing, so a
            // corrected series appeared twice with two different results.
            val correcting = seriesId
            if (correcting != null) {
                when (val result = repository.correct(correcting, content.draft)) {
                    is ApiResult.Success -> {
                        if (content.photo != null) scans.attach(correcting)
                        // A queued series stays queued after a local rewrite; one
                        // already on the server was just corrected there.
                        repository.drainQueue()
                        val stillQueued = repository.myHistory().first()
                            .firstOrNull { it.id == correcting }?.pending == true
                        _uiState.value = content.copy(saving = false, savedPending = stillQueued)
                        onSaved(stillQueued)
                    }
                    // Correcting a series the server already has needs a
                    // connection — unlike recording, it cannot be queued: two
                    // devices editing the same series offline is a different
                    // problem. So say so rather than pretending it saved.
                    is ApiResult.Failure ->
                        _uiState.value = content.copy(saving = false, error = result.error)
                }
                return@launch
            }

            // Always lands in the local queue first. Saving cannot fail for want
            // of a network — that is the entire point on a range in a basement.
            val seriesId = repository.record(
                draft = content.draft,
                memberId = member.id,
                memberLabel = member.label.ifBlank { null },
                sessionId = content.sessionId,
                occurredOn = content.occurredOn,
                discipline = content.discipline,
                recordedAt = ZonedDateTime.now().format(DateTimeFormatter.ISO_OFFSET_DATE_TIME),
                notes = null,
            )
            // The photograph belongs to the series from here on: the shooter
            // can look at the sheet again next to the numbers, and the pair of
            // (crop, corrected shots) is a training example for the detector.
            if (content.photo != null) scans.attach(seriesId)

            val sent = repository.drainQueue()
            _uiState.value = content.copy(saving = false, savedPending = sent == 0)
            onSaved(sent == 0)
        }
    }

    /**
     * Start another series on the same sheet — the two-shooters-one-target case
     * from the range. Keeps session, discipline and target, clears the shots,
     * and drops the member so the next one has to be chosen deliberately.
     */
    fun startNextSeries() = update { content ->
        content.copy(
            draft = content.draft.copy(shots = emptyList()),
            member = if (content.selectableMembers.isEmpty()) content.member else null,
            savedPending = false,
        )
    }

    fun newShotId(): String = UUID.randomUUID().toString()

    private inline fun update(block: (RecordShotsUiState.Content) -> RecordShotsUiState.Content) {
        val content = _uiState.value as? RecordShotsUiState.Content ?: return
        _uiState.value = block(content)
    }

    /** Bullet diameters offered in the picker. */
    val calibers = Calibers.ALL
}
