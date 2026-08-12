import { cookies } from "next/headers"

import { API_BASE, sessionCookieHeader } from "@/lib/api"
import { SESSION_COOKIE } from "@/lib/constants"

/**
 * The invoice file, streamed to the browser.
 *
 * The backend decides who may have it and what it is; this route only carries
 * bytes. Disposition and content type are passed through unchanged — an XML
 * invoice is an attachment there for a reason, and re-deciding it here would
 * be the place that gets it wrong.
 */

export const dynamic = "force-dynamic"
export const runtime = "nodejs"

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
): Promise<Response> {
  const cookieStore = await cookies()
  const session = cookieStore.get(SESSION_COOKIE)?.value
  if (!session) return new Response("Unauthorized", { status: 401 })

  const { id } = await params
  if (!/^[0-9a-f-]{36}$/i.test(id)) {
    return new Response("Invalid id", { status: 422 })
  }

  let upstream: Response
  try {
    upstream = await fetch(`${API_BASE}/api/v1/incoming-invoices/${id}/file`, {
      headers: sessionCookieHeader(session),
      cache: "no-store",
    })
  } catch {
    return new Response("Backend unavailable", { status: 503 })
  }

  if (!upstream.ok || upstream.body === null) {
    return new Response("Not available", { status: upstream.status || 502 })
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type":
        upstream.headers.get("content-type") ?? "application/octet-stream",
      "Content-Disposition":
        upstream.headers.get("content-disposition") ?? "attachment",
      "X-Content-Type-Options": "nosniff",
      "Cache-Control": "no-store",
    },
  })
}
