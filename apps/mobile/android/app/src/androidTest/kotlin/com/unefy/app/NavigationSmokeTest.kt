package com.unefy.app

import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsSelected
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import com.unefy.app.nav.NavPreferences
import com.unefy.app.nav.TopLevel
import com.unefy.app.nav.defaultDestinationsFor
import com.unefy.app.nav.permittedDestinations
import com.unefy.core.designsystem.theme.UnefyTheme
import com.unefy.core.model.ClubRole
import com.unefy.feature.attendance.R as AttendanceR
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

    /**
     * The scanner is no longer a section, so the sweep above cannot reach it.
     * It hangs off the check-in screen's header instead, and that route is the
     * only way in — which makes it worth its own test rather than none.
     */
    @Test
    fun board_reaches_the_scanner_from_the_check_in_screen() {
        show(ClubRole.BOARD)
        openFromMoreShelf(TopLevel.CheckIn)

        composeRule.onNodeWithContentDescription(string(AttendanceR.string.attendance_open_scanner))
            .performClick()
        composeRule.waitForIdle()

        composeRule.onNodeWithText(string(AttendanceR.string.scanner_title)).assertIsDisplayed()
    }

    /**
     * Scanning is not the only way in. Someone always arrives with a flat
     * battery, and the paper list this replaces could always be ticked by hand —
     * so the manual list has to open from the scanner and show real members.
     */
    @Test
    fun the_scanner_offers_a_manual_list() {
        show(ClubRole.BOARD)
        openFromMoreShelf(TopLevel.CheckIn)
        composeRule.onNodeWithContentDescription(string(AttendanceR.string.attendance_open_scanner))
            .performClick()
        composeRule.waitForIdle()

        // By role: a plain text match also hits row labels in the list behind.
        composeRule.onNode(button(string(AttendanceR.string.scanner_manual_action))).performClick()
        composeRule.waitForIdle()

        composeRule.onNodeWithText(string(AttendanceR.string.scanner_manual_title))
            .assertIsDisplayed()
        // The list is populated from the real repository against the mocked
        // engine, so a name here proves the fetch and the decoding, not just
        // that a sheet opened.
        composeRule.onNodeWithText("Test Mitglied").assertIsDisplayed()
    }

    /**
     * The scanner has to answer "who is in the room", not just "someone was
     * scanned" — that is the question the paper list answered.
     */
    @Test
    fun the_scanner_lists_who_is_checked_in() {
        show(ClubRole.BOARD)
        openFromMoreShelf(TopLevel.CheckIn)
        composeRule.onNodeWithContentDescription(string(AttendanceR.string.attendance_open_scanner))
            .performClick()
        composeRule.waitForIdle()

        // Loaded through the real repository and its cache, so the row proves
        // the fetch, the decoding and the merge — not just that a list renders.
        composeRule.onNodeWithText("Erika Beispiel").assertIsDisplayed()
        composeRule.onNodeWithText(string(AttendanceR.string.scanner_row_scanned))
            .assertIsDisplayed()
        // A guest has no member id, and the list once decoded that as a whole
        // or not at all — so the member above disappeared along with them.
        composeRule.onNodeWithText("Jonas Gast").assertIsDisplayed()
    }

    /** A member may hold a code; the way to the scanner must not be offered. */
    @Test
    fun member_is_not_offered_the_scanner() {
        show(ClubRole.MEMBER)
        openFromBar(TopLevel.CheckIn)

        composeRule.onNodeWithContentDescription(string(AttendanceR.string.attendance_open_scanner))
            .assertDoesNotExist()
    }

    private fun openEveryDestination(role: ClubRole) {
        val inBar = show(role)

        inBar.forEach(::openFromBar)
        (permittedDestinations(role) - inBar.toSet()).forEach(::openFromMoreShelf)
    }

    /** Puts the shell on screen with a known bar, and returns what is in it. */
    private fun show(role: ClubRole): List<TopLevel> {
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
        return inBar
    }

    /** A bar tab: tap it, and the bar should report it as the current section. */
    private fun openFromBar(destination: TopLevel) {
        composeRule.onNode(tab(label(destination))).performClick()
        composeRule.waitForIdle()
        composeRule.onNode(tab(label(destination))).assertIsSelected()
    }

    /**
     * A section that is not in the bar: reachable only through "Mehr". The grid's
     * hint is the marker — visible while the shelf is open, gone once the tap has
     * navigated away from it.
     */
    private fun openFromMoreShelf(destination: TopLevel) {
        val hint = string(R.string.nav_more_grid_hint)

        composeRule.onNode(tab(string(R.string.nav_more))).performClick()
        composeRule.waitForIdle()
        composeRule.onNodeWithText(hint).assertIsDisplayed()

        // The tile, unambiguously: the grid only holds sections that are not in
        // the bar, so nothing else on screen carries this label.
        composeRule.onNodeWithText(label(destination)).performClick()
        composeRule.waitForIdle()
        composeRule.onNodeWithText(hint).assertDoesNotExist()
    }

    /**
     * By role, not by text alone: a section's tab and that section's heading
     * carry the same word, so "Termine" matches twice as soon as the Termine
     * screen is open.
     */
    private fun button(label: String) =
        hasText(label) and SemanticsMatcher.expectValue(SemanticsProperties.Role, Role.Button)

    private fun tab(label: String) =
        hasText(label) and SemanticsMatcher.expectValue(SemanticsProperties.Role, Role.Tab)

    private fun label(destination: TopLevel): String = string(destination.label)

    private fun string(id: Int): String = composeRule.activity.getString(id)
}
