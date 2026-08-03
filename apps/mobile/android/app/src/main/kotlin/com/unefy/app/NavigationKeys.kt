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

@Serializable
data object MoreKey : UnefyNavKey
