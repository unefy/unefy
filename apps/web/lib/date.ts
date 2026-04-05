import { format as dateFnsFormat, isValid } from "date-fns"

/**
 * Returns the preferred user-facing date format for the given locale.
 * - `de`: `dd.MM.yyyy` (05.04.2026)
 * - `en` (and everything else): `yyyy-MM-dd` (2026-04-05, ISO 8601)
 */
export function getDateFormat(locale: string): string {
  if (locale.toLowerCase().startsWith("de")) return "dd.MM.yyyy"
  return "yyyy-MM-dd"
}

/**
 * Formats a date (Date or ISO string) for display according to the user's
 * locale. Returns an empty string for invalid input.
 */
export function formatDate(
  date: Date | string | null | undefined,
  locale: string,
): string {
  if (!date) return ""
  const d = typeof date === "string" ? new Date(date) : date
  if (!isValid(d)) return ""
  return dateFnsFormat(d, getDateFormat(locale))
}
