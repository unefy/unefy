package com.unefy.core.push

import com.unefy.core.model.AuthTokens
import com.unefy.core.network.TokenStore
import com.unefy.core.sync.SyncCollection
import com.unefy.core.testing.FakeCoordinator
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.JsonElement
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class WakeupDrainTest {

    /**
     * The wake-up names one entity, but server-side coalescing makes it only
     * the first of a possible burst — so the drain covers everything mirrored.
     */
    @Test
    fun `a wake-up drains every registered collection`() = runTest {
        val coordinator = FakeCoordinator()
        val drain = WakeupDrain(
            coordinator,
            setOf(NamedCollection("members"), NamedCollection("events")),
            emptySet(),
            FakeTokens(signedIn = true),
        )

        assertTrue(drain.drainAll())
        assertEquals(setOf("members", "events"), coordinator.syncedNow.toSet())
    }

    /**
     * The trap named in the plan: a worker that syncs without a session runs
     * into a 401 loop nobody asked for. Signed out means silently nothing.
     */
    @Test
    fun `no session means no sync`() = runTest {
        val coordinator = FakeCoordinator()
        val drain = WakeupDrain(
            coordinator,
            setOf(NamedCollection("members")),
            emptySet(),
            FakeTokens(signedIn = false),
        )

        assertFalse(drain.drainAll())
        assertEquals(emptyList<String>(), coordinator.syncedNow)
    }
}

private class NamedCollection(override val name: String) : SyncCollection {
    override suspend fun apply(changed: List<JsonElement>, deleted: List<String>, generation: Long) =
        Unit

    override suspend fun sweep(generation: Long) = Unit

    override suspend fun clear() = Unit
}

private class FakeTokens(private val signedIn: Boolean) : TokenStore {
    override suspend fun current(): AuthTokens? =
        if (signedIn) {
            AuthTokens(accessToken = "a", refreshToken = "r", accessExpiresAtEpochSeconds = 0)
        } else {
            null
        }

    override suspend fun refresh(): AuthTokens? = current()
}
