export type DocumentTemplate = {
  id: string
  name: string
  title: string
  body: string
  include_letterhead: boolean
  include_footer: boolean
  verifiable: boolean
  is_active: boolean
  created_at: string
  updated_at: string
}

/** One placeholder the editor may offer. The German label lives in the
 * messages, keyed by `key` — the backend only names the set. */
export type DocumentVariable = {
  key: string
  description: string
}

export type TemplatePreview = {
  rendered: string
  /** Names in the text that are not in the set. */
  unknown: string[]
}

export type IssuedDocument = {
  id: string
  member_id: string
  template_id: string | null
  template_name: string
  title: string
  body: string
  issued_at: string
  revoked_at: string | null
  revoke_reason: string | null
  verification_code: string | null
}
