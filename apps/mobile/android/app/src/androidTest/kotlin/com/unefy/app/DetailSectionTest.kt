package com.unefy.app

import androidx.compose.foundation.layout.Column
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import com.unefy.core.designsystem.component.Field
import com.unefy.core.designsystem.component.UnefyDetailSection
import com.unefy.core.designsystem.theme.UnefyTheme
import dagger.hilt.android.testing.HiltAndroidRule
import dagger.hilt.android.testing.HiltAndroidTest
import org.junit.Before
import org.junit.Rule
import org.junit.Test

/**
 * A detail section has to follow the record it is given.
 *
 * Every detail screen shows the same subject twice — a header that reads the
 * model directly, and sections that read it through [UnefyDetailSection]. If the
 * two disagree about which record is current, the screen shows one member's name
 * over another member's address, which is what it did: opening a member after
 * having viewed another one paired the new name with the previous person's
 * contact, address, membership and banking fields.
 *
 * The value arrives as a parameter here rather than as a snapshot read inside the
 * section, because that is how the real screens pass it — `MemberDetailContent`
 * takes a `Member` and the sections close over it.
 */
@HiltAndroidTest
class DetailSectionTest {

    // Nothing here is injected, but the runner swaps in HiltTestApplication for
    // the whole run: a class without the rule throws "The component was not
    // created" as soon as anything reaches for the component, and which test
    // runs first decides whether it does.
    @get:Rule(order = 0)
    val hiltRule = HiltAndroidRule(this)

    @get:Rule(order = 1)
    val composeRule = createComposeRule()

    @Before
    fun setUp() {
        hiltRule.inject()
    }

    @Test
    fun a_section_shows_the_values_of_the_record_it_is_given() {
        val email = mutableStateOf(FIRST)
        composeRule.setContent {
            val current by email
            UnefyTheme { Column { ContactSection(current) } }
        }

        composeRule.onNodeWithText(FIRST).assertIsDisplayed()

        composeRule.runOnIdle { email.value = SECOND }
        composeRule.waitForIdle()

        composeRule.onNodeWithText(SECOND).assertIsDisplayed()
        composeRule.onNodeWithText(FIRST).assertDoesNotExist()
    }

    /**
     * The same section rendered for a record whose field is empty must lose the
     * field — and, being the only field, the whole section with it.
     */
    @Test
    fun a_field_that_empties_disappears_with_its_section() {
        val email = mutableStateOf(FIRST)
        composeRule.setContent {
            val current by email
            UnefyTheme { Column { ContactSection(current) } }
        }

        composeRule.onNodeWithText(LABEL).assertIsDisplayed()

        composeRule.runOnIdle { email.value = "" }
        composeRule.waitForIdle()

        composeRule.onNodeWithText(LABEL).assertDoesNotExist()
        composeRule.onNodeWithText(TITLE).assertDoesNotExist()
    }

    @Composable
    private fun ContactSection(email: String) {
        UnefyDetailSection(title = TITLE, fields = listOf(Field(LABEL, email)))
    }

    private companion object {
        const val TITLE = "Kontakt"
        const val LABEL = "E-Mail"
        const val FIRST = "erste@example.org"
        const val SECOND = "zweite@example.org"
    }
}
