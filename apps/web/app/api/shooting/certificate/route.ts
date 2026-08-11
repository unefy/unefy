import { cookies } from "next/headers"
import { z } from "zod"

import { API_BASE, sessionCookieHeader } from "@/lib/api"
import { SESSION_COOKIE } from "@/lib/constants"

/**
 * Proxies the certificate PDF to the browser, to be opened in its viewer.
 *
 * A route handler rather than a server action because an action cannot answer
 * with a file. Same shape as the range-book and SEPA proxies: session cookie
 * forwarded server-side, backend origin stays private, backend authorization
 * decides — this route only carries bytes.
 */

export const dynamic = "force-dynamic"
export const runtime = "nodejs"

const certificateId = z.string().uuid()

export async function GET(request: Request): Promise<Response> {
  const cookieStore = await cookies()
  const session = cookieStore.get(SESSION_COOKIE)?.value
  if (!session) {
    return new Response("Unauthorized", { status: 401 })
  }

  const parsed = certificateId.safeParse(
    new URL(request.url).searchParams.get("id") ?? ""
  )
  if (!parsed.success) {
    return new Response("Invalid certificate id", { status: 422 })
  }

  // The annex is opt-in and read as a plain flag: anything other than an
  // explicit "true" gets the summary, so a mangled link cannot widen what a
  // document discloses.
  const withDays = new URL(request.url).searchParams.get("details") === "true"

  let upstream: Response
  try {
    upstream = await fetch(
      `${API_BASE}/api/v1/modules/shooting/certificates/${parsed.data}/pdf` +
        (withDays ? "?details=true" : ""),
      { headers: sessionCookieHeader(session), cache: "no-store" }
    )
  } catch {
    return new Response("Backend unavailable", { status: 503 })
  }

  if (!upstream.ok || upstream.body === null) {
    return new Response("Certificate unavailable", {
      status: upstream.status || 502,
    })
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type": upstream.headers.get("content-type") ?? "application/pdf",
      "Content-Disposition":
        upstream.headers.get("content-disposition") ??
        `inline; filename="schiessnachweis.pdf"`,
      "Cache-Control": "no-store",
    },
  })
}
