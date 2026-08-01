import { apiCall } from "@/lib/api"

export type SessionUser = {
  id: string
  name: string | null
  email: string
  image: string | null
  locale: string | null
}

/** The platform admin behind an impersonated session, if any. */
export type Impersonator = {
  id: string
  name: string
  email: string
}

export type Session = {
  user: SessionUser
  tenant_id: string | null
  tenant_name: string | null
  tenant_short_name: string | null
  role: string | null
  needs_onboarding: boolean
  /** Platform operator — may enter the admin area. Never a tenant role. */
  is_superuser: boolean
  /**
   * Set while this session is impersonating. `user` is already the
   * impersonated person, so this names who is actually acting.
   */
  impersonator: Impersonator | null
}

export type TenantMembership = {
  tenant_id: string
  name: string
  short_name: string | null
  role: string
}

/**
 * Resolves the current session against the backend.
 *
 * Note: `/api/v1/auth/me` answers 200 with `data: null` for an unauthenticated
 * request rather than 403, so the absence of a session is signalled by the
 * payload — not by the status code.
 */
export async function getSession(): Promise<Session | null> {
  try {
    const data = await apiCall<Session | null>("/api/v1/auth/me")
    return data ?? null
  } catch {
    // Treat an unreachable or erroring backend as "no session" — the layout
    // then sends the user to the login page instead of rendering a broken shell.
    return null
  }
}

/** Clubs the current user belongs to. Empty when the call fails. */
export async function getTenants(): Promise<TenantMembership[]> {
  try {
    return (await apiCall<TenantMembership[]>("/api/v1/auth/tenants")) ?? []
  } catch {
    return []
  }
}
