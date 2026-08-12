import { cookies } from "next/headers"
import { z } from "zod"

import { API_BASE, sessionCookieHeader } from "@/lib/api"
import { SESSION_COOKIE } from "@/lib/constants"

/**
 * Carries an upload from the browser to the backend.
 *
 * A route handler and not a server action, for one hard reason: Next caps an
 * action's body at 1 MB, and a scanned protocol is several. This is the PDF
 * proxy in reverse — the session cookie is added server-side, the backend
 * origin stays private, and the backend decides who may file what. This route
 * only carries bytes.
 *
 * The body is passed through as it arrives, boundary and all, so nothing is
 * buffered here that the backend is going to buffer anyway.
 */

export const dynamic = "force-dynamic"
export const runtime = "nodejs"

const target = z.object({
  /** Set for a new version of an existing document; absent for a new one. */
  documentId: z.string().uuid().optional(),
})

export async function POST(request: Request): Promise<Response> {
  const cookieStore = await cookies()
  const session = cookieStore.get(SESSION_COOKIE)?.value
  if (!session) {
    return Response.json(
      { error: { code: "UNAUTHORIZED", message: "Not signed in" } },
      { status: 401 }
    )
  }

  const contentType = request.headers.get("content-type")
  if (!contentType?.startsWith("multipart/form-data")) {
    return Response.json(
      { error: { code: "VALIDATION_ERROR", message: "Expected multipart" } },
      { status: 422 }
    )
  }

  const parsed = target.safeParse({
    documentId:
      new URL(request.url).searchParams.get("documentId") ?? undefined,
  })
  if (!parsed.success) {
    return Response.json(
      { error: { code: "VALIDATION_ERROR", message: "Invalid document" } },
      { status: 422 }
    )
  }

  const path = parsed.data.documentId
    ? `/api/v1/library/documents/${parsed.data.documentId}/version`
    : "/api/v1/library/documents"

  let upstream: Response
  try {
    upstream = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { ...sessionCookieHeader(session), "Content-Type": contentType },
      body: request.body,
      // Streaming a request body requires this; without it Node's fetch
      // refuses the call rather than buffering silently.
      duplex: "half",
      cache: "no-store",
    } as RequestInit & { duplex: "half" })
  } catch {
    return Response.json(
      { error: { code: "UNREACHABLE", message: "Backend unavailable" } },
      { status: 503 }
    )
  }

  // The backend's envelope is passed through unchanged — the dialog shows the
  // difference between "file too large" and "club out of space", and that
  // distinction only exists in the code the backend sent.
  const body = await upstream.text()
  return new Response(body, {
    status: upstream.status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  })
}
