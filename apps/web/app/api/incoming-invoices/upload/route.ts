import { cookies } from "next/headers"

import { API_BASE, sessionCookieHeader } from "@/lib/api"
import { SESSION_COOKIE } from "@/lib/constants"

/**
 * Carries an invoice from the browser to the backend.
 *
 * A route handler and not a server action, for the same hard reason as the
 * library's upload beside it: Next caps an action's body at 1 MB and a scanned
 * invoice is several. The body is passed through as it arrives, boundary and
 * all, so nothing is buffered here that the backend is going to buffer anyway.
 */

export const dynamic = "force-dynamic"
export const runtime = "nodejs"

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

  let upstream: Response
  try {
    upstream = await fetch(`${API_BASE}/api/v1/incoming-invoices`, {
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

  // The envelope passes through unchanged: "already recorded", "file too
  // large" and "club out of space" are three different things to say, and the
  // distinction only exists in the code the backend sent.
  const body = await upstream.text()
  return new Response(body, {
    status: upstream.status,
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
    },
  })
}
