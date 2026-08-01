/**
 * Backend base URL for flows that must run as a top-level browser redirect
 * (OAuth), so they cannot be proxied through a Server Action.
 */
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8013"

export const SESSION_COOKIE = "unefy_session"
