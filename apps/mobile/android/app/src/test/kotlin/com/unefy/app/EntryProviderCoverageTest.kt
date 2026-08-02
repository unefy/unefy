package com.unefy.app

import androidx.navigation3.runtime.NavKey
import com.unefy.app.nav.TopLevel
import com.unefy.core.model.ClubRole
import kotlin.reflect.KClass
import kotlin.reflect.full.primaryConstructor
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Every navigation key resolves to a screen.
 *
 * The bug this exists for: `entryProvider` matches keys at runtime, so a
 * destination with no `entry<>` compiles cleanly and throws the first time
 * someone taps it. That shipped once already, on the Wettkämpfe tab. Enumerating
 * [UnefyNavKey]'s sealed subclasses means a new key added without a matching
 * entry fails here rather than on a device.
 */
class EntryProviderCoverageTest {

    private val provider = unefyEntryProvider(
        clubName = "Test",
        role = ClubRole.BOARD,
        accountActions = {},
        onOpen = {},
        onSwitchSection = {},
        onBack = {},
    )

    @Test
    fun `every navigation key has an entry`() {
        val keys = UnefyNavKey::class.sealedSubclasses.map(::instantiate)

        assertTrue("No keys found — reflection over the sealed hierarchy broke.", keys.isNotEmpty())
        assertEquals(NO_MISSING_KEYS, emptyList<String>(), keys.withoutEntries())
    }

    @Test
    fun `every top-level destination has an entry`() {
        // Belt and braces: the bar navigates by TopLevel.key, and nothing forces
        // those keys to be part of the sealed hierarchy above.
        val keys = TopLevel.entries.map { it.key }

        assertEquals(NO_MISSING_KEYS, emptyList<String>(), keys.withoutEntries())
    }

    /**
     * `entryProvider`'s default fallback throws for a key it does not handle, so
     * failing to resolve *is* the missing entry. Collected rather than thrown one
     * at a time so the failure names every gap at once.
     */
    private fun List<NavKey>.withoutEntries(): List<String> =
        filter { key -> runCatching { provider(key) }.isFailure }.map { it.toString() }

    /**
     * Keys are objects or small data classes over strings. Anything else is a
     * deliberate stop: a key carrying richer state needs a decision about what a
     * smoke test should pass, not a guessed default.
     */
    private fun instantiate(type: KClass<out UnefyNavKey>): NavKey {
        type.objectInstance?.let { return it }
        val constructor = requireNotNull(type.primaryConstructor) {
            "${type.simpleName} has neither an object instance nor a primary constructor."
        }
        val arguments = constructor.parameters.associateWith { parameter ->
            require(parameter.type.classifier == String::class) {
                "${type.simpleName}.${parameter.name} is ${parameter.type}; " +
                    "teach EntryProviderCoverageTest how to build it."
            }
            "test"
        }
        return constructor.callBy(arguments)
    }

    private companion object {
        const val NO_MISSING_KEYS = "Navigation keys with no entry<> in unefyEntryProvider"
    }
}
