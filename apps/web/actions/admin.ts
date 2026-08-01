"use server"

import { revalidatePath } from "next/cache"
import { cookies } from "next/headers"
import { redirect } from "next/navigation"
import { z } from "zod"

import type { ActionResult } from "@/actions/auth"
import { SESSION_COOKIE } from "@/lib/constants"

const API_BASE = process.env.API_URL || "http://localhost:8013"

/**
 * Applies the backend's `Set-Cookie` for the session to the browser, honouring
 * the lifetime the backend chose.
 *
 * This matters here in a way it does not elsewhere: an impersonation session
 * lives an hour, and mirroring it with the usual seven-day lifetime would leave
 * the browser holding a cookie long after the session behind it is gone.
 */
async function mirrorSessionCookie(res: Response): Promise<void> {
  const header = res.headers.get("set-cookie")
  if (!header) return

  const match = header.match(new RegExp(`${SESSION_COOKIE}=([^;]*)`))
  if (!match) return

  const cookieStore = await cookies()
  const value = match[1]
  const maxAge = header.match(/Max-Age=(\d+)/i)?.[1]

  // An empty value with Max-Age=0 is the backend clearing the session.
  if (!value || maxAge === "0") {
    cookieStore.delete(SESSION_COOKIE)
    return
  }

  // Backend session tokens are URL-safe base64 — accept nothing else.
  if (!/^[A-Za-z0-9_-]{20,256}$/.test(value)) return

  cookieStore.set(SESSION_COOKIE, value, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: maxAge ? Number(maxAge) : 60 * 60 * 24 * 7,
  })
}

async function adminFetch(path: string, body?: unknown): Promise<Response> {
  const cookieStore = await cookies()
  const sessionCookie = cookieStore.get(SESSION_COOKIE)?.value

  return fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(sessionCookie
        ? { Cookie: `${SESSION_COOKIE}=${sessionCookie}` }
        : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  })
}

const impersonateSchema = z.object({
  user_id: z.string().uuid(),
  tenant_id: z.string().uuid().nullable(),
  reason: z.string().trim().min(3).max(500),
})

export async function impersonateAction(
  _prev: ActionResult | undefined,
  formData: FormData
): Promise<ActionResult> {
  const tenantId = formData.get("tenant_id")
  const parsed = impersonateSchema.safeParse({
    user_id: formData.get("user_id"),
    tenant_id: tenantId ? String(tenantId) : null,
    reason: formData.get("reason"),
  })
  if (!parsed.success) {
    return { success: false, error: "validation" }
  }

  let res: Response
  try {
    res = await adminFetch("/api/v1/admin/impersonate", parsed.data)
  } catch {
    return { success: false, error: "unreachable" }
  }

  if (!res.ok) {
    return {
      success: false,
      error: res.status === 403 ? "forbidden" : "unknown",
    }
  }

  await mirrorSessionCookie(res)
  revalidatePath("/", "layout")
  // Land in the club the admin just stepped into, not back on the admin list.
  redirect("/")
}

export async function stopImpersonationAction(): Promise<ActionResult> {
  let res: Response
  try {
    res = await adminFetch("/api/v1/admin/impersonate/stop")
  } catch {
    return { success: false, error: "unreachable" }
  }

  if (!res.ok) {
    return { success: false, error: "unknown" }
  }

  await mirrorSessionCookie(res)
  const body = (await res.json().catch(() => ({}))) as {
    data?: { restored?: boolean }
  }
  revalidatePath("/", "layout")

  // The admin's own session had already expired — they have to sign in again.
  redirect(body.data?.restored ? "/admin/users" : "/login")
}
