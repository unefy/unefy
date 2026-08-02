package com.unefy.app

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsSelected
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import com.unefy.app.nav.NavPreferences
import com.unefy.app.nav.TopLevel
import com.unefy.app.nav.defaultDestinationsFor
import com.unefy.app.nav.permittedDestinations
import com.unefy.core.designsystem.theme.UnefyTheme
import com.unefy.core.model.ClubRole
import dagger.hilt.android.testing.HiltAndroidRule
import dagger.hilt.android.testing.HiltAndroidTest
import javax.inject.Inject
import kotlinx.coroutines.runBlocking
import org.junit.Before
import org.junit.Rule
import org.junit.Test

/**
 * Opens every destination a role can reach, on a device.
 *
 * The gap this closes: `entryProvider` resolves keys at runtime, screens are
 * only composed when navigated to, and neither the compiler nor a unit test
 * walks the shell. `EntryProviderCoverageTest` proves each key *has* an entry;
 * this proves the entry actually composes — a missing `hiltViewModel` binding, a
 * crashing screen or a broken bar item all fail here and nowhere else.
 *
 * Both roles run, because the permitted sets barely overlap: a member never sees
 * Mitglieder or Beiträge, and a board member never sees Meine Beiträge.
 *
 * Note this writes the navigation arrangement to the device's DataStore — the
 * bar has to be in a known state for the test to know what is in it and what is
 * on the "Mehr" shelf. On a device that also runs the app by hand, that resets
 * the arrangement.
 */
@HiltAndroidTest
class NavigationSmokeTest {

    @get:Rule(order = 0)
    val hiltRule = HiltAndroidRule(this)

    @get:Rule(order = 1)
    val composeRule = createAndroidComposeRule<HiltTestActivity>()

    @Inject
    lateinit var navPreferences: NavPreferences

    @Before
    fun setUp() {
        hiltRule.inject()
    }

    @Test
    fun board_opens_every_permitted_destination() = openEveryDestination(ClubRole.BOARD)

    @Test
    fun member_opens_every_permitted_destination() = openEveryDestination(ClubRole.MEMBER)

    private fun openEveryDestination(role: ClubRole) {
        val inBar = defaultDestinationsFor(role).take(NavPreferences.MAX_VISIBLE)
        runBlocking { navPreferences.setVisibleDestinations(role, inBar) }

        composeRule.setContent {
            UnefyTheme {
                MainNavigation(
                    clubName = "Testverein",
                    accountEmail = "test@example.org",
                    accountName = "Test",
                    role = role,
                    onSignOut = {},
                )
            }
        }

        inBar.forEach(::openFromBar)
        (permittedDestinations(role) - inBar.toSet()).forEach(::openFromMoreShelf)
    }

    /** A bar tab: tap it, and the bar should report it as the current section. */
    private fun openFromBar(destination: TopLevel) {
        composeRule.onNodeWithText(label(destination)).performClick()
        composeRule.waitForIdle()
        composeRule.onNodeWithText(label(destination)).assertIsSelected()
    }

    /**
     * A section that is not in the bar: reachable only through "Mehr". The grid's
     * hint is the marker — visible while the shelf is open, gone once the tap has
     * navigated away from it.
     */
    private fun openFromMoreShelf(destination: TopLevel) {
        val hint = string(R.string.nav_more_grid_hint)

        composeRule.onNodeWithText(string(R.string.nav_more)).performClick()
        composeRule.waitForIdle()
        composeRule.onNodeWithText(hint).assertIsDisplayed()

        composeRule.onNodeWithText(label(destination)).performClick()
        composeRule.waitForIdle()
        composeRule.onNodeWithText(hint).assertDoesNotExist()
    }

    private fun label(destination: TopLevel): String = string(destination.label)

    private fun string(id: Int): String = composeRule.activity.getString(id)
}
