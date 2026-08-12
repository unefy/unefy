import { cookies } from "next/headers"
import { z } from "zod"

import { API_BASE, sessionCookieHeader } from "@/lib/api"
import { SESSION_COOKIE } from "@/lib/constants"

/**
 * Streams a filed document to the browser.
 *
 * Same shape as the certificate PDF proxy: session cookie forwarded
 * server-side, backend origin private, and the backend decides who may read
 * what — a member never receives a committee document, and this route never
 * asks. It only carries bytes.
 *
 * The type and the disposition come from upstream rather than being guessed
 * here: the backend detected the type from the file's own first bytes, and
 * re-deciding it in the proxy is how a PDF ends up being served as whatever
 * the uploader claimed.
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
    upstream = await fetch(`${API_BASE}/api/v1/library/documents/${id}/content`, {
      headers: sessionCookieHeader(session),
      cache: "no-store",
    })
  } catch {
    return new Response("Backend unavailable", { status: 503 })
  }

  if (!upstream.ok || upstream.body === null) {
    return new Response("Document unavailable", {
      status: upstream.status || 502,
    })
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type":
        upstream.headers.get("content-type") ?? "application/octet-stream",
      "Content-Disposition":
        upstream.headers.get("content-disposition") ??
        'attachment; filename="dokument"',
      // Both from upstream in spirit, restated here so a change to the proxy
      // cannot quietly drop them: a club's documents belong in no shared
      // cache, and nothing may be re-typed by guesswork on the way out.
      "X-Content-Type-Options": "nosniff",
      "Cache-Control": "no-store",
    },
  })
}
