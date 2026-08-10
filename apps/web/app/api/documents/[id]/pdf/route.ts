import { cookies } from "next/headers"
import { z } from "zod"

import { API_BASE, sessionCookieHeader } from "@/lib/api"
import { SESSION_COOKIE } from "@/lib/constants"

/**
 * Proxies an issued document's PDF to the browser as a download.
 *
 * A route handler rather than a server action because an action cannot answer
 * with a file. Same shape as the SEPA and range-book proxies: session cookie
 * forwarded server-side, backend origin stays private, and the backend decides
 * who may read what — this route only carries bytes.
 */

export const dynamic = "force-dynamic"
export const runtime = "nodejs"

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
): Promise<Response> {
  const cookieStore = await cookies()
  const session = cookieStore.get(SESSION_COOKIE)?.value
  if (!session) {
    return new Response("Unauthorized", { status: 401 })
  }

  const { id } = await params
  if (!z.string().uuid().safeParse(id).success) {
    return new Response("Invalid document", { status: 422 })
  }

  let upstream: Response
  try {
    upstream = await fetch(`${API_BASE}/api/v1/documents/${id}/pdf`, {
      headers: sessionCookieHeader(session),
      cache: "no-store",
    })
  } catch {
    return new Response("Backend unavailable", { status: 503 })
  }

  if (!upstream.ok || upstream.body === null) {
    const detail = await upstream.text().catch(() => "")
    return new Response(detail || "Document unavailable", {
      status: upstream.status || 502,
      headers: { "Content-Type": "application/json" },
    })
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition":
        upstream.headers.get("content-disposition") ??
        'attachment; filename="dokument.pdf"',
      // A document about one person has no business in a shared cache.
      "Cache-Control": "no-store",
    },
  })
}
