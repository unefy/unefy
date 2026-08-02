package com.unefy.core.model

/**
 * One entry of the club directory as a member sees it.
 *
 * A distinct type from [Member] on purpose, mirroring the backend's separate
 * schema: the directory carries names and category and nothing else, and a type
 * that cannot hold an address cannot leak one.
 */
data class DirectoryEntry(
    val id: String,
    val firstName: String,
    val lastName: String,
    val category: String?,
) {
    val displayName: String get() = "$firstName $lastName"

    val initials: String
        get() = listOf(firstName, lastName)
            .mapNotNull { it.firstOrNull()?.uppercase() }
            .joinToString(separator = "")
}
