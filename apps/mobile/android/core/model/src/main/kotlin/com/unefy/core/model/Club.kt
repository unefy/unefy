package com.unefy.core.model

/**
 * The club as the app needs it, including which sport modules are active.
 *
 * [modules] is the union over the club's sports. The app must not assume any
 * particular sport: a module-specific screen is shown when its key is present
 * and never otherwise.
 */
data class Club(
    val id: String,
    val name: String,
    val shortName: String?,
    val sports: List<ClubSport>,
    val modules: List<String>,
) {
    fun hasModule(key: String): Boolean = key in modules

    /** The sport to show when only one fits — primary first, else the first listed. */
    val primarySport: ClubSport?
        get() = sports.firstOrNull { it.isPrimary } ?: sports.firstOrNull()
}

data class ClubSport(
    val id: String,
    val key: String,
    val name: String,
    val isPrimary: Boolean,
)

/** Module keys the app knows how to render. Anything else is ignored. */
object ClubModules {
    const val SHOOTING = "shooting"
}
