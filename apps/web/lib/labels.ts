/**
 * Canonical enum values the backend stores, mirrored here so raw keys never
 * reach the UI.
 *
 * `memberStatus` matches `MEMBER_STATUS_KEYS` in `app/core/seeds.py`, `role`
 * matches the RBAC roles in `app/dependencies.py`. A value the backend adds
 * without a translation here falls back to the raw key rather than rendering
 * blank — visibly wrong beats invisibly missing.
 */
export const MEMBER_STATUS_KEYS = [
  "active",
  "inactive",
  "resigned",
  "terminated",
  "deceased",
] as const

export const ROLE_KEYS = ["owner", "admin", "board", "member"] as const

export const GENDER_KEYS = ["male", "female", "diverse"] as const

type Translate = (key: string) => string

/** Resolves `admin.memberStatus.<key>`, falling back to the raw key. */
export function memberStatusLabel(t: Translate, key: string): string {
  return (MEMBER_STATUS_KEYS as readonly string[]).includes(key)
    ? t(`memberStatus.${key}`)
    : key
}

/** Resolves `admin.gender.<key>`, falling back to the raw key. */
export function genderLabel(t: Translate, key: string): string {
  return (GENDER_KEYS as readonly string[]).includes(key)
    ? t(`gender.${key}`)
    : key
}

/** Resolves `admin.roles.<key>`, falling back to the raw key. */
export function roleLabel(t: Translate, key: string): string {
  return (ROLE_KEYS as readonly string[]).includes(key)
    ? t(`roles.${key}`)
    : key
}
