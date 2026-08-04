import { cookies } from "next/headers"

import { API_BASE, sessionCookieHeader } from "@/lib/api"
import { SESSION_COOKIE } from "@/lib/constants"
import { rangeBookQuerySchema } from "@/lib/shooting-schema"

/**
 * Proxies the range-book CSV to the browser as a download.
 *
 * A route handler rather than a server action because an action cannot answer
 * with a file. Same shape as the stream proxy (`app/api/stream/route.ts`):
 * session cookie forwarded server-side, backend origin stays private, backend
 * authorization (module + role) decides — this route only carries bytes.
 */

export const dynamic = "force-dynamic"
export const runtime = "nodejs"

export async function GET(request: Request): Promise<Response> {
  const cookieStore = await cookies()
  const session = cookieStore.get(SESSION_COOKIE)?.value
  if (!session) {
    return new Response("Unauthorized", { status: 401 })
  }

  const url = new URL(request.url)
  const parsed = rangeBookQuerySchema.safeParse({
    from: url.searchParams.get("from") ?? "",
    to: url.searchParams.get("to") ?? "",
  })
  if (!parsed.success) {
    return new Response("Invalid date range", { status: 422 })
  }

  let upstream: Response
  try {
    upstream = await fetch(
      `${API_BASE}/api/v1/modules/shooting/range-book?from=${parsed.data.from}&to=${parsed.data.to}`,
      { headers: sessionCookieHeader(session), cache: "no-store" }
    )
  } catch {
    return new Response("Backend unavailable", { status: 503 })
  }

  if (!upstream.ok || upstream.body === null) {
    return new Response("Export unavailable", { status: upstream.status || 502 })
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type": upstream.headers.get("content-type") ?? "text/csv",
      "Content-Disposition":
        upstream.headers.get("content-disposition") ??
        `attachment; filename="standbuch_${parsed.data.from}_${parsed.data.to}.csv"`,
      "Cache-Control": "no-store",
    },
  })
}
