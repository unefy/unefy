"use server"

import { z } from "zod"

import { SESSION_COOKIE } from "@/lib/constants"
import { revalidatePath } from "next/cache"
import { cookies } from "next/headers"
import { redirect } from "next/navigation"

const API_BASE = process.env.API_URL || "http://localhost:8013"

export type ActionResult<T = unknown> =
  { success: true; data?: T } | { success: false; error: string }

/**
 * Forwards the session cookie from browser → backend and, on response,
 * mirrors any Set-Cookie for `unefy_session` back to the browser so the
 * backend can rotate sessions transparently.
 */
async function forwardedFetch(
  path: string,
  init: RequestInit
): Promise<Response> {
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

  const setCookieHeader = res.headers.get("set-cookie")
  if (setCookieHeader) {
    const match = setCookieHeader.match(new RegExp(`${SESSION_COOKIE}=([^;]+)`))
    // Backend session tokens are URL-safe base64 — accept nothing else.
    if (match && /^[A-Za-z0-9_-]{20,256}$/.test(match[1])) {
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

const magicLinkSchema = z.object({
  email: z.string().email(),
})

export async function requestMagicLinkAction(
  _prev: ActionResult | undefined,
  formData: FormData
): Promise<ActionResult> {
  const parsed = magicLinkSchema.safeParse({ email: formData.get("email") })
  if (!parsed.success) {
    return { success: false, error: "invalidEmail" }
  }

  let res: Response
  try {
    res = await forwardedFetch("/api/v1/auth/magic-link/request", {
      method: "POST",
      body: JSON.stringify({ email: parsed.data.email }),
    })
  } catch {
    return { success: false, error: "unreachable" }
  }

  if (!res.ok) {
    return { success: false, error: "unknown" }
  }
  return { success: true }
}

export async function signOutAction(): Promise<void> {
  // Best-effort: the backend revokes the session server-side, but the local
  // cookie is cleared either way so the user is signed out of this browser.
  try {
    await forwardedFetch("/api/v1/auth/logout", { method: "POST" })
  } catch {
    // ignored — cookie removal below is what matters for the client
  }

  const cookieStore = await cookies()
  cookieStore.delete(SESSION_COOKIE)
  redirect("/login")
}

const switchTenantSchema = z.object({ tenant_id: z.string().uuid() })

export async function switchTenantAction(
  tenantId: string
): Promise<ActionResult> {
  const parsed = switchTenantSchema.safeParse({ tenant_id: tenantId })
  if (!parsed.success) {
    return { success: false, error: "validation" }
  }

  let res: Response
  try {
    res = await forwardedFetch("/api/v1/auth/switch-tenant", {
      method: "POST",
      body: JSON.stringify({ tenant_id: parsed.data.tenant_id }),
    })
  } catch {
    return { success: false, error: "unreachable" }
  }

  if (!res.ok) {
    return { success: false, error: "unknown" }
  }

  revalidatePath("/", "layout")
  return { success: true }
}
