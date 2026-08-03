package com.unefy.core.designsystem.theme

import java.math.BigDecimal
import java.text.NumberFormat
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.format.FormatStyle
import java.util.Currency
import java.util.Locale

/**
 * Display formatting for values that arrive from the API as strings.
 *
 * Every method is total: malformed input returns the raw string rather than
 * throwing. A backend that sends an unexpected date must not crash a list.
 */
object UnefyFormat {

    fun dateTime(iso: String?): String = iso?.let {
        runCatching {
            Instant.parse(it)
                .atZone(ZoneId.systemDefault())
                .format(DateTimeFormatter.ofLocalizedDateTime(FormatStyle.MEDIUM, FormatStyle.SHORT))
        }.getOrElse { _ -> date(iso) }
    }.orEmpty()

    /** Time of day only — for the end of a range whose date the start names. */
    fun time(iso: String?): String = iso?.let {
        runCatching {
            Instant.parse(it)
                .atZone(ZoneId.systemDefault())
                .format(DateTimeFormatter.ofLocalizedTime(FormatStyle.SHORT))
        }.getOrElse { _ -> it }
    }.orEmpty()

    fun date(iso: String?): String = iso?.let {
        runCatching {
            LocalDate.parse(it.take(DATE_LENGTH))
                .format(DateTimeFormatter.ofLocalizedDate(FormatStyle.MEDIUM))
        }.getOrElse { _ -> it }
    }.orEmpty()

    /** Money is formatted, never computed with. The string from the API is authoritative. */
    fun money(amount: String?, currencyCode: String = "EUR"): String = amount?.let {
        runCatching {
            NumberFormat.getCurrencyInstance(Locale.getDefault()).apply {
                currency = Currency.getInstance(currencyCode)
            }.format(BigDecimal(it))
        }.getOrElse { _ -> it }
    }.orEmpty()

    private const val DATE_LENGTH = 10
}
