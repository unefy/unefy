package com.unefy.app

import androidx.navigation3.runtime.NavKey
import kotlinx.serialization.Serializable

/**
 * Navigation 3 keys. Typed and serializable, so the back stack survives process
 * death without a bundle-parsing layer.
 *
 * Sealed, and every key lives in this file: that is what lets
 * `EntryProviderCoverageTest` enumerate the destinations and prove the
 * `entryProvider` handles each one. A key with no matching `entry<>` compiles
 * fine and throws the moment someone taps it — the sealed hierarchy turns that
 * runtime crash into a failing test.
 */
sealed interface UnefyNavKey : NavKey

@Serializable
data object MembersKey : UnefyNavKey

@Serializable
data class MemberDetailKey(val memberId: String) : UnefyNavKey

/**
 * Creating a member and editing one, which are the same screen.
 *
 * A null [memberId] means create. One key rather than two, because the
 * difference the screen makes of it is a title and a verb.
 */
@Serializable
data class MemberFormKey(val memberId: String? = null) : UnefyNavKey

@Serializable
data object EventsKey : UnefyNavKey

@Serializable
data class EventDetailKey(val eventId: String) : UnefyNavKey

@Serializable
data object DuesKey : UnefyNavKey

@Serializable
data object ProfileKey : UnefyNavKey

@Serializable
data object DirectoryKey : UnefyNavKey

@Serializable
data object MyDuesKey : UnefyNavKey

@Serializable
data object CompetitionsKey : UnefyNavKey

@Serializable
data class CompetitionDetailKey(
    val competitionId: String,
    val competitionName: String,
) : UnefyNavKey

@Serializable
data class ScoreboardKey(val competitionId: String, val competitionName: String) : UnefyNavKey

/** The member's own rotating check-in code. */
@Serializable
data object AttendanceCodeKey : UnefyNavKey

/** The supervisor's scanner. Board and above — see permittedDestinations. */
@Serializable
data object ScannerKey : UnefyNavKey

/** The member's own range history, incl. self-kept entries. Shooting clubs only. */
@Serializable
data object MyRangeDaysKey : UnefyNavKey

/**
 * One session's attendance list, opened from the scanner. Carries the title so
 * the screen can say which evening it shows without a second fetch.
 */
@Serializable
data class AttendanceListKey(val sessionId: String, val sessionTitle: String) : UnefyNavKey

/** The member's own recorded shot series. Shooting clubs. */
@Serializable
data object ShotHistoryKey : UnefyNavKey

/**
 * Recording a series on the digital target.
 *
 * Every parameter is a String because `EntryProviderCoverageTest` builds each
 * key reflectively and only knows how to supply strings. `sessionId` empty means
 * free training — the server creates the container itself.
 */
@Serializable
data class RecordShotsKey(
    val sessionId: String = "",
    val discipline: String = "",
    val memberId: String = "",
    /** Set to correct a series that is already recorded; empty records a new one. */
    val seriesId: String = "",
) : UnefyNavKey

/** One recorded series, full size. */
@Serializable
data class SeriesDetailKey(val seriesId: String) : UnefyNavKey

@Serializable
data object MoreKey : UnefyNavKey
