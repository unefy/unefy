export interface Club {
  id: string
  name: string
  short_name: string | null
  slug: string
  email: string | null
  phone: string | null
  website: string | null
  street: string | null
  zip_code: string | null
  city: string | null
  state: string | null
  country: string | null
  description: string | null
  logo_url: string | null
  founded_at: string | null
  registration_number: string | null
  registration_court: string | null
  tax_number: string | null
  tax_office: string | null
  is_nonprofit: boolean
  nonprofit_since: string | null
  member_number_format: string
  member_number_prefix: string | null
  member_number_next: number
  member_statuses: string | null
}

export interface MemberStatusOption {
  key: string
  label: string
}

// Keys that are used in code logic (badge variants, defaults, etc.)
// and can never be removed from the list.
export const PROTECTED_STATUS_KEYS = new Set(["active", "inactive"])

// Known keys whose label is managed via i18n (members.<translationKey>).
// For any key listed here, getStatusLabel returns the translated string
// and the user cannot edit the label in the UI.
// Only keys in this map have their label managed via i18n and are treated
// as locked system entries in the settings UI. Other seed statuses are
// normal user content (editable label, removable).
export const STATUS_TRANSLATIONS: Record<string, string> = {
  active: "statusActive",
  inactive: "statusInactive",
}

export const DEFAULT_MEMBER_STATUSES: MemberStatusOption[] = [
  { key: "active", label: "Aktiv" },
  { key: "inactive", label: "Inaktiv" },
  { key: "resigned", label: "Ausgetreten" },
  { key: "terminated", label: "Gekündigt" },
  { key: "deceased", label: "Verstorben" },
]

export function parseMemberStatuses(json: string | null): MemberStatusOption[] {
  if (!json) return DEFAULT_MEMBER_STATUSES
  try {
    const parsed = JSON.parse(json)
    if (!Array.isArray(parsed)) return DEFAULT_MEMBER_STATUSES
    const result: MemberStatusOption[] = parsed.filter(
      (s): s is MemberStatusOption =>
        typeof s?.key === "string" && typeof s?.label === "string",
    )
    // Ensure protected system statuses are always present
    for (const sys of DEFAULT_MEMBER_STATUSES) {
      if (PROTECTED_STATUS_KEYS.has(sys.key) && !result.find((s) => s.key === sys.key)) {
        result.unshift(sys)
      }
    }
    return result
  } catch {
    return DEFAULT_MEMBER_STATUSES
  }
}

export function isProtectedStatus(key: string): boolean {
  return PROTECTED_STATUS_KEYS.has(key)
}

export function hasStatusTranslation(key: string): boolean {
  return key in STATUS_TRANSLATIONS
}

export function getStatusLabel(
  status: MemberStatusOption,
  t: (key: string) => string,
): string {
  const translationKey = STATUS_TRANSLATIONS[status.key]
  return translationKey ? t(translationKey) : status.label
}

export function slugifyStatusKey(label: string): string {
  const slug = label
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/ß/g, "ss")
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
  return slug || "status"
}
