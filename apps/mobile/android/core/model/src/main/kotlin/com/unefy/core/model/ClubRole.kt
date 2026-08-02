package com.unefy.core.model

/**
 * The caller's role inside the club.
 *
 * The backend gates 43 of its endpoints on `board` or above, so this is not a
 * cosmetic distinction: showing an administrative section to a plain member
 * produces a wall of 403s, not a degraded experience.
 */
enum class ClubRole(val apiValue: String) {
    OWNER("owner"),
    ADMIN("admin"),
    BOARD("board"),
    MEMBER("member"),

    /** An unknown role is treated as the least privileged, never the most. */
    UNKNOWN(""),
    ;

    /** Whether the account may see club-wide administrative data. */
    val canAdminister: Boolean
        get() = this == OWNER || this == ADMIN || this == BOARD

    companion object {
        fun fromApi(value: String?): ClubRole =
            entries.firstOrNull { it.apiValue.equals(value, ignoreCase = true) } ?: UNKNOWN
    }
}
