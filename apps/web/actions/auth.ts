"use server"

import { cookies } from "next/headers"
import { z } from "zod"

const API_BASE = process.env.API_URL || "http://localhost:8008"
const SESSION_COOKIE = "unefy_session"

export type ActionResult<T = unknown> =
  | { success: true; data?: T }
  | {
      success: false
      error: string
      fieldErrors?: Record<string, string[]>
    }

/**
 * Forwards the session cookie from browser → backend and, on response,
 * mirrors any Set-Cookie for `unefy_session` back to the browser so the
 * backend can rotate sessions transparently.
 */
async function forwardedFetch(path: string, init: RequestInit): Promise<Response> {
  const cookieStore = await cookies()
  const sessionCookie = cookieStore.get(SESSION_COOKIE)?.value

  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(sessionCookie
        ? { Cookie: `${SESSION_COOKIE}=${sessionCookie}` }
        : {}),
      ...init.headers,
    },
  })

  // Mirror a rotated session cookie back to the browser.
  const setCookieHeader = res.headers.get("set-cookie")
  if (setCookieHeader) {
    const match = setCookieHeader.match(
      new RegExp(`${SESSION_COOKIE}=([^;]+)`),
    )
    if (match) {
      cookieStore.set(SESSION_COOKIE, match[1], {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        path: "/",
        maxAge: 60 * 60 * 24 * 7,
      })
    }
  }

  return res
}

// ---------------------------------------------------------------------------

const createClubSchema = z.object({
  club_name: z
    .string()
    .trim()
    .min(2, { message: "tooShort" })
    .max(255, { message: "tooLong" }),
})

export async function createClubAction(
  _prev: ActionResult | undefined,
  formData: FormData,
): Promise<ActionResult<{ tenant_id: string; slug: string }>> {
  const parsed = createClubSchema.safeParse({
    club_name: formData.get("club_name"),
  })
  if (!parsed.success) {
    return {
      success: false,
      error: "validation",
      fieldErrors: parsed.error.flatten().fieldErrors,
    }
  }

  const res = await forwardedFetch("/api/v1/auth/onboarding/create-club", {
    method: "POST",
    body: JSON.stringify({ club_name: parsed.data.club_name }),
  })

  if (!res.ok) {
    const body: unknown = await res.json().catch(() => ({}))
    const code =
      typeof body === "object" && body !== null && "error" in body
        ? (body as { error?: { code?: string } }).error?.code
        : undefined
    return { success: false, error: code ?? "unknown" }
  }

  const body = (await res.json()) as {
    data: { tenant_id: string; name: string; slug: string }
  }
  return {
    success: true,
    data: { tenant_id: body.data.tenant_id, slug: body.data.slug },
  }
}

// ---------------------------------------------------------------------------

const magicLinkSchema = z.object({
  email: z.string().email(),
})

export async function requestMagicLinkAction(
  _prev: ActionResult | undefined,
  formData: FormData,
): Promise<ActionResult> {
  const parsed = magicLinkSchema.safeParse({
    email: formData.get("email"),
  })
  if (!parsed.success) {
    return { success: false, error: "validation" }
  }

  const res = await forwardedFetch("/api/v1/auth/magic-link/request", {
    method: "POST",
    body: JSON.stringify({ email: parsed.data.email }),
  })

  if (!res.ok) {
    return { success: false, error: "unknown" }
  }
  return { success: true }
}
