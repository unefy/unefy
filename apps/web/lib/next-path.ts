/**
 * Cookie used to carry a post-login redirect target across the OAuth
 * roundtrip, since the backend decides where its callback lands and cannot
 * pass a target back to us. Short-lived and consumed on first use.
 */
export const LOGIN_NEXT_COOKIE = "unefy_login_next"

/** Where an authenticated user lands when no valid target is given. */
export const APP_HOME = "/"

/**
 * Validates a post-login redirect target.
 *
 * Only same-origin paths are accepted. Everything else is rejected so that
 * `?next=` cannot be abused as an open redirect: absolute URLs, protocol
 * relative `//evil.com`, backslash variants like `/\evil.com` and
 * `javascript:` all resolve to a foreign (or null) origin and are dropped.
 *
 * Returns the normalized `pathname + search`, or `null` if unusable.
 */
export function safeNextPath(value: string | null | undefined): string | null {
  if (!value || !value.startsWith("/") || value.startsWith("//")) return null

  let url: URL
  try {
    url = new URL(value, "http://localhost")
  } catch {
    return null
  }
  if (url.origin !== "http://localhost") return null

  const path = `${url.pathname}${url.search}`

  // Never bounce back to the login page — that would loop.
  if (
    path === "/login" ||
    path.startsWith("/login/") ||
    path.startsWith("/login?")
  ) {
    return null
  }
  // A target equal to the default carries no information.
  if (path === APP_HOME) return null

  return path
}
