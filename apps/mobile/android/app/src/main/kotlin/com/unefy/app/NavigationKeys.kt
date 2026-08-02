package com.unefy.app

import androidx.navigation3.runtime.NavKey
import kotlinx.serialization.Serializable

/**
 * Navigation 3 keys. Typed and serializable, so the back stack survives process
 * death without a bundle-parsing layer.
 */
@Serializable
data object MembersKey : NavKey

@Serializable
data class MemberDetailKey(val memberId: String) : NavKey

@Serializable
data object EventsKey : NavKey

@Serializable
data object DuesKey : NavKey

@Serializable
data object ProfileKey : NavKey

@Serializable
data object DirectoryKey : NavKey

@Serializable
data object MyDuesKey : NavKey

@Serializable
data object CompetitionsKey : NavKey

@Serializable
data class ScoreboardKey(val competitionId: String, val competitionName: String) : NavKey

@Serializable
data object MoreKey : NavKey
