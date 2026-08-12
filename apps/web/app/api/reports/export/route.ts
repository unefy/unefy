import { cookies } from "next/headers"

import { API_BASE, sessionCookieHeader } from "@/lib/api"
import { SESSION_COOKIE } from "@/lib/constants"

/**
 * Proxies the annual report's spreadsheet to the browser as a download.
 *
 * A route handler rather than a server action, for the same reason as the SEPA
 * export beside it: an action cannot answer with a file. The session cookie is
 * forwarded server-side, the backend origin stays private, and the backend
 * decides who may have it — this route only carries bytes.
 */

export const dynamic = "force-dynamic"
export const runtime = "nodejs"

export async function GET(request: Request): Promise<Response> {
  const cookieStore = await cookies()
  const session = cookieStore.get(SESSION_COOKIE)?.value
  if (!session) {
    return new Response("Unauthorized", { status: 401 })
  }

  // Parsed rather than forwarded: the value lands in a filename and a query,
  // and a year is four digits or it is nothing.
  const raw = new URL(request.url).searchParams.get("year") ?? ""
  const year = Number(raw)
  if (!/^\d{4}$/.test(raw) || year < 2000 || year > 2100) {
    return new Response("Invalid year", { status: 422 })
  }

  let upstream: Response
  try {
    upstream = await fetch(
      `${API_BASE}/api/v1/reports/annual/export?year=${year}`,
      { headers: sessionCookieHeader(session), cache: "no-store" }
    )
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
      "Content-Type":
        upstream.headers.get("content-type") ?? "text/csv; charset=utf-8",
      "Content-Disposition":
        upstream.headers.get("content-disposition") ??
        `attachment; filename="jahresbericht-${year}.csv"`,
      "Cache-Control": "no-store",
    },
  })
}
