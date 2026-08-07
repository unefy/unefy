package com.unefy.app.theme

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.themeDataStore: DataStore<Preferences> by
    preferencesDataStore(name = "unefy_theme")

/**
 * Light, dark, or whatever the system says.
 *
 * [SYSTEM] stays the default: following the device is what Android users expect,
 * and it is the only setting that keeps up with a scheduled night mode. The
 * override exists for the people whose device is set one way and who want this
 * app the other — most often the range, where a dark screen at dusk is easier on
 * the eyes than a phone that has not switched over yet.
 */
enum class ThemeMode(val id: String) {
    SYSTEM("system"),
    LIGHT("light"),
    DARK("dark"),
    ;

    fun isDark(systemInDark: Boolean): Boolean = when (this) {
        SYSTEM -> systemInDark
        LIGHT -> false
        DARK -> true
    }

    companion object {
        fun fromId(id: String?): ThemeMode = entries.firstOrNull { it.id == id } ?: SYSTEM
    }
}

/**
 * The chosen appearance, on the device rather than on the account.
 *
 * Same reasoning as [com.unefy.app.nav.NavPreferences]: it describes this screen,
 * not the club, and a tablet and a phone may reasonably disagree.
 *
 * Stored as the stable id, never as the ordinal — an enum reordered in a future
 * release must not silently flip somebody into dark mode.
 */
@Singleton
class ThemePreferences @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    val mode: Flow<ThemeMode> =
        context.themeDataStore.data.map { prefs -> ThemeMode.fromId(prefs[KEY]) }

    suspend fun setMode(mode: ThemeMode) {
        context.themeDataStore.edit { prefs -> prefs[KEY] = mode.id }
    }

    private companion object {
        val KEY = stringPreferencesKey("theme_mode")
    }
}
