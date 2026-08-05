package com.unefy.core.model

/**
 * A club member. A deliberately lean subset of the backend's `MemberResponse` —
 * the fields the app actually shows. Banking and address details are fetched
 * only where a screen needs them, mirroring how the iOS models are kept small.
 */
data class Member(
    val id: String,
    val memberNumber: String,
    val firstName: String,
    val lastName: String,
    val email: String?,
    val phone: String?,
    val mobile: String?,
    val birthday: String?,
    val gender: String?,
    val street: String?,
    val zipCode: String?,
    val city: String?,
    val status: MemberStatus,
    val category: String?,
    val joinedAt: String,
    val leftAt: String?,
    val iban: String?,
) {
    val postalLine: String?
        get() = listOfNotNull(zipCode, city).takeIf { it.isNotEmpty() }?.joinToString(" ")

    /**
     * Only the last four digits. An admin needs to recognise the account, not to
     * read it out — showing a full IBAN on a screen in a clubhouse is a leak
     * waiting to happen.
     */
    val maskedIban: String?
        get() = iban?.takeIf { it.length > IBAN_VISIBLE }?.let {
            "•••• " + it.takeLast(IBAN_VISIBLE)
        } ?: iban
    val displayName: String get() = "$firstName $lastName"

    val initials: String
        get() = listOf(firstName, lastName)
            .mapNotNull { it.firstOrNull()?.uppercase() }
            .joinToString(separator = "")

    private companion object {
        const val IBAN_VISIBLE = 4
    }
}

/**
 * The backend stores status as a free-form `String(20)`, so an unrecognised
 * value must not crash the app — it degrades to [UNKNOWN] and is shown as-is.
 */
enum class MemberStatus(val apiValue: String) {
    ACTIVE("active"),
    INACTIVE("inactive"),
    RESIGNED("resigned"),
    PENDING("pending"),
    UNKNOWN(""),
    ;

    companion object {
        fun fromApi(value: String?): MemberStatus =
            entries.firstOrNull { it.apiValue.equals(value, ignoreCase = true) } ?: UNKNOWN
    }
}
