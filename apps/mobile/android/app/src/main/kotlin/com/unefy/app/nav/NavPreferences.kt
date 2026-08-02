package com.unefy.app.nav

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.unefy.core.model.ClubRole
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.navDataStore: DataStore<Preferences> by preferencesDataStore(name = "unefy_nav")

/**
 * Which sections a person keeps in the navigation bar, and in what order.
 *
 * Stored on the device rather than on the account: it is a display preference,
 * not data about the club, and keeping it local avoids a schema decision about
 * how an account that belongs to two clubs would hold two different orders.
 *
 * Persisted as stable ids, never as ordinals — an enum reordered in a future
 * release must not silently rearrange someone's bar. Ids the current role cannot
 * reach are dropped on read, so switching clubs cannot strand a tab pointing at
 * something forbidden.
 */
@Singleton
class NavPreferences @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    fun visibleDestinations(role: ClubRole): Flow<List<TopLevel>> =
        context.navDataStore.data.map { prefs ->
            val permitted = permittedDestinations(role)
            val stored = prefs[key(role)]
                ?.split(SEPARATOR)
                ?.filter { it.isNotBlank() }
                ?.mapNotNull { id -> permitted.firstOrNull { it.id == id } }
                ?.distinct()

            stored?.takeIf { it.isNotEmpty() }?.take(MAX_VISIBLE)
                ?: defaultDestinationsFor(role).take(MAX_VISIBLE)
        }

    suspend fun setVisibleDestinations(role: ClubRole, destinations: List<TopLevel>) {
        context.navDataStore.edit { prefs ->
            prefs[key(role)] = destinations.take(MAX_VISIBLE).joinToString(SEPARATOR) { it.id }
        }
    }

    /**
     * Per role, because the permitted set differs: a board member's arrangement
     * would be meaningless once they are only a member.
     */
    private fun key(role: ClubRole) = stringPreferencesKey("visible_${role.apiValue}")

    companion object {
        /** Four chosen sections plus the fixed "more" tab — Material's limit is five. */
        const val MAX_VISIBLE = 4
        private const val SEPARATOR = ","
    }
}
