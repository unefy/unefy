import { cookies } from "next/headers"

const API_BASE = process.env.API_URL || "http://localhost:8008"
const COOKIE_NAME = "unefy_session"

export interface User {
  id: string
  name: string
  email: string
  image?: string | null
  locale?: string | null
}

export interface Session {
  user: User
  tenant_id: string | null
  tenant_name: string | null
  tenant_short_name: string | null
  role: string | null
  needs_onboarding: boolean
}

/**
 * Get the current session from the backend by forwarding the session cookie.
 * Returns null if not authenticated.
 */
export async function getSession(): Promise<Session | null> {
  try {
    const cookieStore = await cookies()
    const sessionCookie = cookieStore.get(COOKIE_NAME)?.value

    if (!sessionCookie) return null

    const res = await fetch(`${API_BASE}/api/v1/auth/me`, {
      headers: { Cookie: `${COOKIE_NAME}=${sessionCookie}` },
      cache: "no-store",
    })

    if (!res.ok) return null

    const json = await res.json()
    return json.data as Session | null
  } catch {
    return null
  }
}
