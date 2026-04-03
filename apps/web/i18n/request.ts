import { getRequestConfig } from "next-intl/server"
import { cookies, headers } from "next/headers"

export const locales = ["de", "en"] as const
export type Locale = (typeof locales)[number]
export const defaultLocale: Locale = "de"

function getBrowserLocale(acceptLanguage: string | null): Locale | null {
  if (!acceptLanguage) return null
  for (const part of acceptLanguage.split(",")) {
    const lang = part.split(";")[0].trim().substring(0, 2).toLowerCase()
    if (locales.includes(lang as Locale)) return lang as Locale
  }
  return null
}

export default getRequestConfig(async () => {
  const cookieStore = await cookies()
  const headerStore = await headers()

  // Priority: cookie > browser language > default
  const cookieLocale = cookieStore.get("locale")?.value
  const browserLocale = getBrowserLocale(headerStore.get("accept-language"))

  const locale =
    cookieLocale && locales.includes(cookieLocale as Locale)
      ? cookieLocale
      : browserLocale || defaultLocale

  return {
    locale,
    messages: (await import(`../messages/${locale}.json`)).default,
  }
})
