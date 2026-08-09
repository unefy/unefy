import { NextResponse, type NextRequest } from "next/server"

import { SESSION_COOKIE } from "@/lib/constants"
import { APP_HOME, LOGIN_NEXT_COOKIE, safeNextPath } from "@/lib/next-path"

/**
 * Routes reachable without a session. Everything else is protected by
 * default, so a newly added route is gated unless it is listed here.
 */
const PUBLIC_ROUTES = ["/login", "/verify"]

/**
 * Public routes that a *signed-in* visitor must still reach.
 *
 * Only the login page bounces someone who already has a session — the
 * certificate check does not. A board member scanning the QR on a printout is
 * the likeliest reader of that page, and sending them to the dashboard instead
 * would answer a question they did not ask.
 */
const SIGNED_OUT_ONLY = ["/login"]

// Backend session tokens are URL-safe base64 — anything else is treated as
// no session at all, so a garbage cookie cannot pass the gate.
const SESSION_TOKEN = /^[A-Za-z0-9_-]{20,256}$/

/**
 * Reads the parked redirect target. The value is written URL-encoded (a raw
 * path could contain `;` and truncate the cookie), so decode before
 * validating — tolerating an already-decoded value either way.
 */
function readParkedNext(request: NextRequest): string | null {
  const raw = request.cookies.get(LOGIN_NEXT_COOKIE)?.value
  if (!raw) return null

  let decoded: string
  try {
    decoded = decodeURIComponent(raw)
  } catch {
    decoded = raw
  }
  return safeNextPath(decoded)
}

/**
 * Optimistic auth gate. This only checks whether a plausible session cookie
 * is present — it does NOT verify the session, because the proxy runs on
 * every request (including prefetches) and a backend roundtrip here would be
 * a per-navigation cost. Actual verification belongs in the server components
 * that read `/api/v1/auth/me`.
 */
export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl

  const token = request.cookies.get(SESSION_COOKIE)?.value
  const hasSession = token !== undefined && SESSION_TOKEN.test(token)

  const matches = (routes: string[]) =>
    routes.some(
      (route) => pathname === route || pathname.startsWith(`${route}/`)
    )

  const isPublicRoute = matches(PUBLIC_ROUTES)

  // Signed in but sitting on the login page — send them into the app, honouring
  // an explicit `?next=` if it points somewhere legitimate.
  if (hasSession && matches(SIGNED_OUT_ONLY)) {
    const target = safeNextPath(request.nextUrl.searchParams.get("next"))
    return NextResponse.redirect(new URL(target ?? APP_HOME, request.nextUrl))
  }

  // Signed in and heading for the app home: consume a target parked before an
  // OAuth handoff, since the backend callback always lands on the home route.
  if (hasSession && pathname === APP_HOME) {
    const parked = readParkedNext(request)
    if (parked) {
      const response = NextResponse.redirect(new URL(parked, request.nextUrl))
      response.cookies.delete(LOGIN_NEXT_COOKIE)
      return response
    }
  }

  // No session on a protected route — send them to the login page and remember
  // where they were headed.
  if (!hasSession && !isPublicRoute) {
    const loginUrl = new URL("/login", request.nextUrl)
    const target = safeNextPath(`${pathname}${search}`)
    if (target) loginUrl.searchParams.set("next", target)
    return NextResponse.redirect(loginUrl)
  }

  return NextResponse.next()
}

export const config = {
  // Skip API routes, Next internals and static assets (e.g. the login cover).
  matcher: [
    "/((?!api|_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)",
  ],
}
