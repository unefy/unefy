import { cookies } from "next/headers"
import { z } from "zod"

import { API_BASE, sessionCookieHeader } from "@/lib/api"
import { SESSION_COOKIE } from "@/lib/constants"

/**
 * Proxies the Art. 15 data bundle to the browser as a download.
 *
 * A route handler rather than a server action because an action cannot answer
 * with a file. Same shape as the SEPA and range-book proxies: session cookie
 * forwarded server-side, backend origin stays private, and the backend decides
 * who may read whose data — this route only carries bytes.
 *
 * Without `member`, the caller exports their own. With it, the backend
 * enforces the board role; passing an id is not itself permission.
 */

export const dynamic = "force-dynamic"
export const runtime = "nodejs"

export async function GET(request: Request): Promise<Response> {
  const cookieStore = await cookies()
  const session = cookieStore.get(SESSION_COOKIE)?.value
  if (!session) {
    return new Response("Unauthorized", { status: 401 })
  }

  const memberId = new URL(request.url).searchParams.get("member")
  if (memberId !== null && !z.string().uuid().safeParse(memberId).success) {
    return new Response("Invalid member", { status: 422 })
  }

  const path = memberId
    ? `/api/v1/members/${memberId}/export`
    : "/api/v1/members/me/export"

  let upstream: Response
  try {
    upstream = await fetch(`${API_BASE}${path}`, {
      headers: sessionCookieHeader(session),
      cache: "no-store",
    })
  } catch {
    return new Response("Backend unavailable", { status: 503 })
  }

  if (!upstream.ok || upstream.body === null) {
    const detail = await upstream.text().catch(() => "")
    return new Response(detail || "Export unavailable", {
      status: upstream.status || 502,
      headers: { "Content-Type": "application/json" },
    })
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type": "application/json",
      "Content-Disposition":
        upstream.headers.get("content-disposition") ??
        'attachment; filename="unefy-export.json"',
      // A copy of somebody's personal data has no business in any cache.
      "Cache-Control": "no-store",
    },
  })
}
