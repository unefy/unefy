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

    fun date(iso: String?): String = date(iso, ZoneId.systemDefault())

    /**
     * A day, from either a plain date or an instant.
     *
     * The two are not the same string and must not be handled the same way. A
     * plain `2026-03-01` carries no zone and is simply that day. An instant
     * does, and cutting it to its first ten characters prints the day it was in
     * UTC: a consent recorded at 01:20 in Berlin was recorded on the 12th, and
     * the trail below it said so while this line said the 11th. Only visible in
     * the two hours after midnight, which is exactly why it is worth a branch.
     *
     * [zone] is a parameter so a test can assert a day without depending on the
     * machine it runs on.
     */
    internal fun date(iso: String?, zone: ZoneId): String = iso?.let {
        runCatching {
            Instant.parse(it).atZone(zone).toLocalDate()
        }.recoverCatching { _ ->
            LocalDate.parse(it.take(DATE_LENGTH))
        }.map { day ->
            day.format(DateTimeFormatter.ofLocalizedDate(FormatStyle.MEDIUM))
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
