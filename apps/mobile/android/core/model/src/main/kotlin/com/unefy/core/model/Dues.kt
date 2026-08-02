package com.unefy.core.model

/**
 * A single membership fee item.
 *
 * [amount] stays a string exactly as the backend sends it ("120.00"). Money is
 * never parsed into a Double on the way through — it is formatted for display
 * and otherwise passed along untouched.
 */
data class DuesEntry(
    val id: String,
    val memberId: String,
    val memberName: String,
    val feeName: String,
    val amount: String,
    val dueDate: String?,
    val status: DuesStatus,
    val paidAt: String?,
)

enum class DuesStatus(val apiValue: String) {
    OPEN("open"),
    PAID("paid"),
    CANCELLED("cancelled"),
    OVERDUE("overdue"),
    UNKNOWN(""),
    ;

    companion object {
        fun fromApi(value: String?): DuesStatus =
            entries.firstOrNull { it.apiValue.equals(value, ignoreCase = true) } ?: UNKNOWN
    }
}

data class DuesSummary(
    val openCount: Int,
    val openAmount: String,
    val paidCount: Int,
    val paidAmount: String,
)
