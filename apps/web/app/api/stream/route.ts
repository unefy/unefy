import { cookies } from "next/headers"

import { SESSION_COOKIE } from "@/lib/constants"

/**
 * Proxies the backend's change stream to the browser.
 *
 * The first route handler in this app, and the BFF pattern is why it has to
 * exist rather than the browser connecting to the backend directly. The session
 * cookie is set by Next on Next's own origin (`actions/auth.ts`) and forwarded
 * server-side as a `Cookie` header; in development that is `:3000` talking to
 * `:8013`, two different origins, so a browser `EventSource` pointed at the
 * backend would carry no credentials at all. `NEXT_PUBLIC_API_URL` exists for
 * OAuth top-level redirects and nothing else (`lib/constants.ts`).
 *
 * Proxying keeps the backend origin private and the auth story identical to
 * every other read in the app.
 */

// Never prerender or cache: this response is a connection, not a document.
export const dynamic = "force-dynamic"

// Node, not Edge. The stream is long-lived and holds no per-request state, but
// Edge would add a second runtime to reason about for no benefit here.
export const runtime = "nodejs"

const API_URL = process.env.API_URL || "http://localhost:8013"

export async function GET(request: Request): Promise<Response> {
  const cookieStore = await cookies()
  const session = cookieStore.get(SESSION_COOKIE)?.value

  if (!session) {
    return new Response("Unauthorized", { status: 401 })
  }

  const headers: HeadersInit = {
    Accept: "text/event-stream",
    Cookie: `${SESSION_COOKIE}=${session}`,
  }

  // Forwarded so a reconnect resumes exactly where it dropped instead of
  // silently skipping whatever happened during the gap.
  const lastEventId = request.headers.get("last-event-id")
  if (lastEventId) {
    headers["Last-Event-ID"] = lastEventId
  }

  let upstream: Response
  try {
    upstream = await fetch(`${API_URL}/api/v1/stream`, {
      headers,
      // Without this the browser navigating away leaves the upstream connection
      // open until it times out, and the per-user stream cap fills up after
      // three reloads.
      signal: request.signal,
      cache: "no-store",
    })
  } catch {
    // A backend restart during development is routine. 503 rather than 500: the
    // client's job is to retry, which EventSource does on its own.
    return new Response("Event stream unavailable", { status: 503 })
  }

  if (!upstream.ok || upstream.body === null) {
    return new Response("Event stream unavailable", { status: upstream.status || 502 })
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-store, no-transform",
      Connection: "keep-alive",
      // Belt and braces alongside the backend's own header: whichever proxy sits
      // in front of Next also needs telling not to buffer.
      "X-Accel-Buffering": "no",
    },
  })
}
