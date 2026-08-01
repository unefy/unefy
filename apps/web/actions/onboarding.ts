"use server"

import { revalidatePath } from "next/cache"
import { cookies } from "next/headers"
import { z } from "zod"

import type { ActionResult } from "@/actions/auth"
import { SESSION_COOKIE } from "@/lib/constants"

const API_BASE = process.env.API_URL || "http://localhost:8013"

const schema = z.object({
  club_name: z.string().trim().min(2).max(255),
  has_divisions: z.boolean(),
  divisions: z
    .array(
      z.object({
        name: z.string().trim().min(1).max(255),
        sport_key: z.string().min(2),
      })
    )
    .min(1)
    .max(20),
})

export async function createClubAction(
  input: z.input<typeof schema>
): Promise<ActionResult<{ slug: string }>> {
  const parsed = schema.safeParse(input)
  if (!parsed.success) {
    return { success: false, error: "validation" }
  }

  const cookieStore = await cookies()
  const sessionCookie = cookieStore.get(SESSION_COOKIE)?.value

  let res: Response
  try {
    res = await fetch(`${API_BASE}/api/v1/auth/onboarding/create-club`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(sessionCookie
          ? { Cookie: `${SESSION_COOKIE}=${sessionCookie}` }
          : {}),
      },
      body: JSON.stringify(parsed.data),
      cache: "no-store",
    })
  } catch {
    return { success: false, error: "unreachable" }
  }

  // Creating a club upgrades the caller to owner, so the backend rotates the
  // session. Mirroring the new cookie is what makes the next request land in
  // the new club instead of the tenant-less onboarding session.
  const setCookie = res.headers.get("set-cookie")
  if (setCookie) {
    const match = setCookie.match(new RegExp(`${SESSION_COOKIE}=([^;]+)`))
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

  if (!res.ok) {
    if (res.status === 429) return { success: false, error: "rateLimited" }
    if (res.status === 422) return { success: false, error: "validation" }
    return { success: false, error: "unknown" }
  }

  const body = (await res.json().catch(() => ({}))) as {
    data?: { slug?: string }
  }
  revalidatePath("/", "layout")
  return { success: true, data: { slug: body.data?.slug ?? "" } }
}
