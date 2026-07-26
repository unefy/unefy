"use server"

import { cookies } from "next/headers"

import { apiCall } from "@/lib/api"

export async function updateLocaleAction(locale: string): Promise<void> {
  if (locale !== "de" && locale !== "en") return

  const cookieStore = await cookies()
  cookieStore.set("locale", locale, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 365,
  })

  try {
    await apiCall("/api/v1/auth/me/locale", {
      method: "PATCH",
      body: JSON.stringify({ locale }),
    })
  } catch {
    // Cookie is already set — backend persistence is best-effort.
  }
}
