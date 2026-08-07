package com.unefy.feature.scoring

import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.format.FormatStyle

/**
 * When a series was shot, read in the reader's own timezone.
 *
 * Two shapes have to be parsed: the server sends an offset ("+00:00"), the app's
 * own queue writes an instant ("Z"). A series whose stamp cannot be read is not
 * dropped — the callers below fall back to showing it raw, because a row that
 * disappears is worse than a row with an ugly date.
 */
private fun parse(recordedAt: String): LocalDateTime? =
    runCatching { Instant.parse(recordedAt) }
        .recoverCatching { OffsetDateTime.parse(recordedAt).toInstant() }
        .getOrNull()
        ?.let { LocalDateTime.ofInstant(it, ZoneId.systemDefault()) }

/** The day a series belongs to, for grouping. Null when the stamp is unreadable. */
internal fun recordedDay(recordedAt: String): LocalDate? = parse(recordedAt)?.toLocalDate()

/**
 * The time of day alone.
 *
 * What a row shows once the list is grouped by day: the date is already above it
 * in the heading, and repeating it on every row pushed the shooter's name out to
 * where it stopped being the first thing read.
 */
internal fun formatRecordedTime(recordedAt: String): String =
    parse(recordedAt)?.format(TIME) ?: recordedAt.take(10)

/**
 * Date and time together — for the detail screen, which has no heading above it
 * to carry the day.
 */
internal fun formatRecordedAt(recordedAt: String): String =
    parse(recordedAt)?.format(DATE_TIME) ?: recordedAt.take(10)

internal fun formatDay(day: LocalDate): String = day.format(DATE)

private val TIME: DateTimeFormatter = DateTimeFormatter.ofLocalizedTime(FormatStyle.SHORT)
private val DATE: DateTimeFormatter = DateTimeFormatter.ofLocalizedDate(FormatStyle.FULL)
private val DATE_TIME: DateTimeFormatter =
    DateTimeFormatter.ofLocalizedDateTime(FormatStyle.MEDIUM, FormatStyle.SHORT)
