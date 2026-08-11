import { cookies } from "next/headers"
import { z } from "zod"

import { API_BASE, sessionCookieHeader } from "@/lib/api"
import { SESSION_COOKIE } from "@/lib/constants"

/**
 * Proxies a donation receipt's PDF to the browser, to be opened in its viewer.
 *
 * Same shape as the other file proxies: session cookie forwarded
 * server-side, backend origin stays private, the backend decides who may read
 * what — this route only carries bytes.
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
    return new Response("Invalid receipt", { status: 422 })
  }

  let upstream: Response
  try {
    upstream = await fetch(`${API_BASE}/api/v1/donations/${id}/pdf`, {
      headers: sessionCookieHeader(session),
      cache: "no-store",
    })
  } catch {
    return new Response("Backend unavailable", { status: 503 })
  }

  if (!upstream.ok || upstream.body === null) {
    const detail = await upstream.text().catch(() => "")
    return new Response(detail || "Receipt unavailable", {
      status: upstream.status || 502,
      headers: { "Content-Type": "application/json" },
    })
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition":
        upstream.headers.get("content-disposition") ??
        'inline; filename="zuwendungsbestaetigung.pdf"',
      // A document naming a person and an amount has no business in a cache.
      "Cache-Control": "no-store",
    },
  })
}
