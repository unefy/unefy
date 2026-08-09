import { cookies } from "next/headers"

import { API_BASE, sessionCookieHeader } from "@/lib/api"
import { SESSION_COOKIE } from "@/lib/constants"
import { sepaExportQuerySchema } from "@/lib/due-schema"

/**
 * Proxies the SEPA pain.008 direct debit file to the browser as a download.
 *
 * A route handler rather than a server action because an action cannot answer
 * with a file. Same shape as the range-book proxy: session cookie forwarded
 * server-side, backend origin stays private, backend authorization decides —
 * this route only carries bytes.
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
  const parsed = sepaExportQuerySchema.safeParse({
    year: url.searchParams.get("year") ?? "",
    collection_date: url.searchParams.get("collection_date") ?? "",
  })
  if (!parsed.success) {
    return new Response("Invalid export parameters", { status: 422 })
  }

  const params = new URLSearchParams({ year: String(parsed.data.year) })
  if (parsed.data.collection_date) {
    params.set("collection_date", parsed.data.collection_date)
  }

  let upstream: Response
  try {
    upstream = await fetch(`${API_BASE}/api/v1/dues/sepa-export?${params}`, {
      headers: sessionCookieHeader(session),
      cache: "no-store",
    })
  } catch {
    return new Response("Backend unavailable", { status: 503 })
  }

  if (!upstream.ok || upstream.body === null) {
    // 422 is the ordinary case here, not a fault: incomplete creditor data, or
    // no open due with a mandate behind it. The message is the backend's.
    const detail = await upstream.text().catch(() => "")
    return new Response(detail || "Export unavailable", {
      status: upstream.status || 502,
      headers: { "Content-Type": "application/json" },
    })
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type": upstream.headers.get("content-type") ?? "application/xml",
      "Content-Disposition":
        upstream.headers.get("content-disposition") ??
        `attachment; filename="sepa-lastschrift-${parsed.data.year}.xml"`,
      // How many transactions the file carries — shown after the download.
      "X-Transaction-Count":
        upstream.headers.get("x-transaction-count") ?? "0",
      "Cache-Control": "no-store",
    },
  })
}
