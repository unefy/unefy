package com.unefy.feature.attendance

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.first

private val Context.installDataStore: DataStore<Preferences> by preferencesDataStore(
    name = "unefy_install",
)

/**
 * A random id for this installation, sent with a scan as check-in context.
 *
 * Not a device fingerprint, deliberately. The phone model is close to worthless
 * as a fraud signal — there are tens of thousands of identical ones — while the
 * pattern that actually matters is "one installation checked twelve different
 * members in tonight". A random id catches that and identifies nobody.
 *
 * It is reset by clearing app data, which is fine: the id exists to correlate
 * scans within a short retention window, not to bind anyone permanently.
 */
fun interface DeviceIdentity {
    suspend fun installId(): String
}

@Singleton
class DefaultDeviceIdentity @Inject constructor(
    @ApplicationContext private val context: Context,
) : DeviceIdentity {
    @Volatile
    private var cached: String? = null

    /**
     * Suspending rather than blocking: this is read on the scan path, which
     * runs on the main dispatcher, and DataStore is disk I/O. Cached after the
     * first read so the disk is touched once per process, not once per code.
     */
    override suspend fun installId(): String = cached ?: run {
        val stored = context.installDataStore.data.first()[KEY]
        val id = stored ?: UUID.randomUUID().toString().also { fresh ->
            context.installDataStore.edit { it[KEY] = fresh }
        }
        cached = id
        id
    }

    private companion object {
        val KEY = stringPreferencesKey("install_id")
    }
}
