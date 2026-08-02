package com.unefy.app.nav

import androidx.annotation.DrawableRes
import androidx.annotation.StringRes
import androidx.navigation3.runtime.NavKey
import com.unefy.app.CompetitionsKey
import com.unefy.app.DirectoryKey
import com.unefy.app.DuesKey
import com.unefy.app.EventsKey
import com.unefy.app.MembersKey
import com.unefy.app.MyDuesKey
import com.unefy.app.ProfileKey
import com.unefy.app.R
import com.unefy.core.designsystem.R as DesignR
import com.unefy.core.model.ClubRole

/**
 * Top-level destinations. An enum rather than a list of keys so the navigation
 * bar and the back stack cannot drift apart.
 */
enum class TopLevel(
    /** Stable across reordering and releases — it is what gets persisted. */
    val id: String,
    val key: NavKey,
    @StringRes val label: Int,
    @DrawableRes val icon: Int,
) {
    // Member-facing
    Profile("profile", ProfileKey, R.string.nav_profile, DesignR.drawable.ic_person),
    Directory("directory", DirectoryKey, R.string.nav_directory, DesignR.drawable.ic_group),
    MyDues("my_dues", MyDuesKey, R.string.nav_my_dues, DesignR.drawable.ic_payments),

    // Shared
    Events("events", EventsKey, R.string.nav_events, DesignR.drawable.ic_event),

    Competitions("competitions", CompetitionsKey, R.string.nav_competitions, DesignR.drawable.ic_trophy),

    // Administrative
    Members("members", MembersKey, R.string.nav_members, DesignR.drawable.ic_group),
    Dues("dues", DuesKey, R.string.nav_dues, DesignR.drawable.ic_payments),
}

/**
 * What the signed-in role may see.
 *
 * Not cosmetic: the backend gates the administrative endpoints on board and
 * above, so offering them to a member produces 403 screens. The member set is
 * what the self-service endpoints actually support.
 */
fun defaultDestinationsFor(role: ClubRole): List<TopLevel> = if (role.canAdminister) {
    listOf(TopLevel.Members, TopLevel.Events, TopLevel.Competitions, TopLevel.Dues)
} else {
    // Competitions rather than the directory: the ranking is what a member opens
    // the app for. The directory stays reachable, just not as a tab.
    listOf(TopLevel.Profile, TopLevel.Events, TopLevel.Competitions, TopLevel.MyDues)
}

/**
 * Which destinations a role may see at all.
 *
 * Distinct from what the user chose to show: the role decides the *permitted*
 * set, the preference orders and filters within it. A stored preference for a
 * destination the role cannot reach is ignored rather than honoured.
 */
fun permittedDestinations(role: ClubRole): List<TopLevel> = if (role.canAdminister) {
    listOf(
        TopLevel.Members,
        TopLevel.Events,
        TopLevel.Competitions,
        TopLevel.Dues,
        TopLevel.Directory,
        TopLevel.Profile,
    )
} else {
    listOf(
        TopLevel.Profile,
        TopLevel.Events,
        TopLevel.Competitions,
        TopLevel.MyDues,
        TopLevel.Directory,
    )
}
