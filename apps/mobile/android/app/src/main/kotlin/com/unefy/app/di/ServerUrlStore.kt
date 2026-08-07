package com.unefy.app.di

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.unefy.app.BuildConfig
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.runBlocking

private val Context.serverDataStore: DataStore<Preferences> by
    preferencesDataStore(name = "unefy_server")

private val SERVER_URL = stringPreferencesKey("base_url")

/**
 * Which backend this installation talks to.
 *
 * The build ships with one ([BuildConfig.API_BASE_URL]) and that is what almost
 * everybody uses. The override exists because the same app has to reach a club's
 * own server: unefy is self-hostable, and a self-hosted club cannot be asked to
 * build their own APK to change a hostname.
 *
 * Not a secret, so plain DataStore rather than the Keystore treatment tokens
 * get — but it is the address credentials are sent to, which is why changing it
 * ends the session (see `LoginViewModel.useServer`).
 */
@Singleton
class ServerUrlStore @Inject constructor(
    @ApplicationContext private val context: Context,
) {

    @Volatile
    private var cached: String? = null

    /**
     * The address to use for the next request.
     *
     * Read from disk once, on first use, and blocking — deliberately. Every HTTP
     * client in the graph is built from this value, so it has to be answerable
     * without a coroutine, and returning the default while the real one loads
     * would send a self-hosted club's first request to the wrong host. It is a
     * single small preferences file, read once per process.
     */
    fun current(): String = cached ?: runBlocking { load() }

    /** The stored address, or the built-in one when nothing was ever set. */
    private suspend fun load(): String =
        context.serverDataStore.data
            .map { it[SERVER_URL] ?: DEFAULT }
            .first()
            .also { cached = it }

    suspend fun set(url: String) {
        val cleaned = normalise(url)
        context.serverDataStore.edit { it[SERVER_URL] = cleaned }
        cached = cleaned
    }

    /** Back to what the build shipped with. */
    suspend fun reset() {
        context.serverDataStore.edit { it.remove(SERVER_URL) }
        cached = DEFAULT
    }

    val isDefault: Boolean get() = current() == DEFAULT

    companion object {
        val DEFAULT: String get() = BuildConfig.API_BASE_URL

        /**
         * What a person types is not what Ktor needs.
         *
         * A trailing slash makes every path double up, and an address without a
         * scheme is not a URL at all — people type "test.unefy.app", so assume
         * https rather than rejecting it. Plain http is left alone: a self-hosted
         * server on a LAN may well not have a certificate.
         */
        fun normalise(input: String): String {
            val trimmed = input.trim().trimEnd('/')
            // Empty stays empty rather than standing in for the default: this
            // has to be a cleaning function only, or [isValid] ends up calling
            // an empty field valid because it silently became a real URL.
            // Getting back to the shipped address is what `reset` is for.
            if (trimmed.isEmpty()) return ""
            return if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
                trimmed
            } else {
                "https://$trimmed"
            }
        }

        /**
         * Enough of a URL to be worth saving. Deliberately loose — a hostname
         * with no dot is a normal thing on a club's own network — but host and
         * port are checked apart, because together they hide their own faults:
         * "https://" normalises to "https://https:", which passes any test that
         * only asks whether something is left after the scheme.
         */
        fun isValid(input: String): Boolean {
            val candidate = normalise(input)
            if (candidate.isEmpty()) return false

            val authority = candidate.substringAfter("://").substringBefore('/')
            if (authority.isBlank() || authority.contains(' ')) return false

            if (!authority.contains(':')) return true

            val host = authority.substringBeforeLast(':')
            val port = authority.substringAfterLast(':')
            return host.isNotBlank() &&
                !host.contains(':') &&
                port.isNotEmpty() &&
                port.all(Char::isDigit)
        }
    }
}
