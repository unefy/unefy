package com.unefy.feature.attendance

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.unefy.core.auth.TokenCrypto
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.first
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

private val Context.seedDataStore: DataStore<Preferences> by preferencesDataStore(
    name = "unefy_attendance_seed",
)

@Serializable
private data class StoredSeed(
    val memberRef: String,
    val seed: String,
    val tenantId: String,
    val expiresAt: Long,
)

/**
 * Keeps the check-in seed across restarts, encrypted.
 *
 * It has to be stored at all because the whole point is offline operation: a
 * member arriving at a basement range with no signal must still be able to show
 * a code. It has to be *encrypted* because a seed is a bearer credential —
 * anyone holding it can generate that member's codes for the rest of the day,
 * and plain DataStore is readable on a rooted device. Reuses the Keystore key
 * from `core:auth` rather than minting a second one.
 */
@Singleton
class SeedStore @Inject constructor(
    @ApplicationContext private val context: Context,
    private val crypto: TokenCrypto,
) {
    private val json = Json { ignoreUnknownKeys = true }

    /**
     * Last seed read or written, for callers that cannot suspend.
     *
     * The NFC card service is one: `processCommandApdu` runs on the main thread
     * and has milliseconds before the reader gives up, which is not enough to
     * open DataStore and decrypt. Populated by [read] and [write], both of
     * which run long before a tap.
     */
    @Volatile
    var cached: AttendanceSeed? = null
        private set

    suspend fun read(): AttendanceSeed? {
        val encrypted = context.seedDataStore.data.first()[KEY] ?: return null
        val plaintext = crypto.decrypt(encrypted) ?: return null
        // A stored seed that no longer parses is a format change, not a crash:
        // the app fetches a fresh one.
        val stored = runCatching { json.decodeFromString<StoredSeed>(plaintext) }.getOrNull()
            ?: return null
        return AttendanceSeed(
            memberRef = stored.memberRef,
            seed = stored.seed,
            tenantId = stored.tenantId,
            expiresAtEpochSeconds = stored.expiresAt,
        ).also { cached = it }
    }

    suspend fun write(seed: AttendanceSeed) {
        val payload = json.encodeToString(
            StoredSeed(
                memberRef = seed.memberRef,
                seed = seed.seed,
                tenantId = seed.tenantId,
                expiresAt = seed.expiresAtEpochSeconds,
            ),
        )
        context.seedDataStore.edit { it[KEY] = crypto.encrypt(payload) }
        cached = seed
    }

    /** On sign-out. The next account must not inherit the last one's code. */
    suspend fun clear() {
        context.seedDataStore.edit { it.remove(KEY) }
        cached = null
    }

    private companion object {
        val KEY = stringPreferencesKey("seed")
    }
}
