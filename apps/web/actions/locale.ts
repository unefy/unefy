"use server"

import { revalidatePath } from "next/cache"
import { cookies } from "next/headers"

import { locales, type Locale } from "@/i18n/request"

export async function updateLocaleAction(locale: string): Promise<void> {
  if (!locales.includes(locale as Locale)) return

  const cookieStore = await cookies()
  cookieStore.set("locale", locale, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 365,
  })

  // The locale is resolved in the root layout from this cookie, so the whole
  // tree has to re-render for the new language to take effect.
  revalidatePath("/", "layout")
}
