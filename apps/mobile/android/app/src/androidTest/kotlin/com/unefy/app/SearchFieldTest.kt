package com.unefy.app

import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.test.assertTextEquals
import androidx.compose.ui.test.hasSetTextAction
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextInput
import com.unefy.core.designsystem.R as DesignR
import com.unefy.core.designsystem.component.UnefySearchField
import com.unefy.core.designsystem.component.rememberSearchFieldState
import com.unefy.core.designsystem.theme.UnefyTheme
import androidx.test.platform.app.InstrumentationRegistry
import dagger.hilt.android.testing.HiltAndroidRule
import dagger.hilt.android.testing.HiltAndroidTest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import org.junit.Before
import org.junit.Rule
import org.junit.Test

/**
 * A search field has to keep what was typed, in the order it was typed.
 *
 * The collaborator answers late on purpose. That is the real shape of every
 * search screen in this app: a keystroke reaches a view model, which filters a
 * Room query and emits a result some frames later. As a controlled field —
 * `value` from the view model, `onValueChange` back into it — the field was
 * re-rendered with the *stale* text in between, which discarded the keystroke
 * and put the cursor back to position 0. On the device that showed up as
 * reordering, because the echo did arrive between two human keystrokes and the
 * next character then landed in front of the previous ones: "beck" became
 * "eckb". Under this test the echo never wins the race at all and the field
 * simply stays empty — the same defect, read at a different speed.
 *
 * Typing is deliberately one character at a time; a single committed string
 * never triggered either.
 */
@HiltAndroidTest
class SearchFieldTest {

    // See DetailSectionTest: HiltTestApplication is the application for the
    // whole run, so every class needs the rule even when it injects nothing.
    @get:Rule(order = 0)
    val hiltRule = HiltAndroidRule(this)

    @get:Rule(order = 1)
    val composeRule = createComposeRule()

    @Before
    fun setUp() {
        hiltRule.inject()
    }

    @Test
    fun typing_survives_a_filter_that_answers_late() {
        val filtered = MutableStateFlow("")

        composeRule.setContent {
            val scope = rememberCoroutineScope()
            val state = rememberSearchFieldState { typed ->
                // Off the UI dispatcher and behind a delay: a filter that has
                // not answered yet must not be able to disturb the field.
                scope.launch(Dispatchers.Default) {
                    delay(FILTER_LAG_MS)
                    filtered.value = typed
                }
            }
            UnefyTheme { UnefySearchField(state = state, placeholder = PLACEHOLDER) }
        }

        val field = composeRule.onNode(hasSetTextAction())
        TYPED.forEach { character ->
            field.performTextInput(character.toString())
            composeRule.waitForIdle()
        }

        field.assertTextEquals(TYPED)
        // And the filter still hears about it — owning the text must not mean
        // keeping it to itself.
        composeRule.waitUntil(TIMEOUT_MS) { filtered.value == TYPED }
    }

    /** The pill's own clear button empties the field and says so. */
    @Test
    fun clearing_empties_the_field_and_reaches_the_filter() {
        val filtered = MutableStateFlow("")

        composeRule.setContent {
            val scope = rememberCoroutineScope()
            val state = rememberSearchFieldState { typed ->
                scope.launch(Dispatchers.Default) { filtered.value = typed }
            }
            UnefyTheme { UnefySearchField(state = state, placeholder = PLACEHOLDER) }
        }

        composeRule.onNode(hasSetTextAction()).performTextInput(TYPED)
        composeRule.waitUntil(TIMEOUT_MS) { filtered.value == TYPED }

        composeRule.onNodeWithContentDescription(clearLabel()).performClick()
        composeRule.waitForIdle()

        composeRule.onNode(hasSetTextAction()).assertTextEquals("")
        composeRule.waitUntil(TIMEOUT_MS) { filtered.value.isEmpty() }
    }

    private fun clearLabel(): String = InstrumentationRegistry.getInstrumentation()
        .targetContext.getString(DesignR.string.search_clear)

    private companion object {
        const val TYPED = "beck"
        const val PLACEHOLDER = "Suchen"
        const val FILTER_LAG_MS = 50L
        const val TIMEOUT_MS = 5_000L
    }
}
