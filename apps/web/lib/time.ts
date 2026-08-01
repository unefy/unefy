/**
 * Time formatting for attendance.
 *
 * Attendance times are evidence, so they must read the same everywhere: in the
 * server-rendered HTML, in the browser, and for two board members sitting in
 * different places. Formatting in whatever zone the runtime happens to be in
 * would break all three — the server runs in UTC and would render an evening
 * session two hours early.
 *
 * The zone therefore comes from the club record (`tenants.timezone`), never
 * from the environment.
 */

/** Used only when the club record could not be read. */
export const FALLBACK_TIME_ZONE = "UTC"

export function formatTime(
  value: string,
  locale: string,
  timeZone: string
): string {
  return new Intl.DateTimeFormat(locale, {
    timeStyle: "short",
    timeZone,
  }).format(new Date(value))
}

export function formatDateTime(
  value: string,
  locale: string,
  timeZone: string
): string {
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone,
  }).format(new Date(value))
}

export function formatDate(
  value: string,
  locale: string,
  timeZone: string
): string {
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeZone,
  }).format(new Date(value))
}
