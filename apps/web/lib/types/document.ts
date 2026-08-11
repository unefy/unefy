/**
 * How a document ends. There is deliberately no signature graphic: a stored
 * club signature would be a reusable forgery tool, and every PDF would carry
 * it back out. The check code is what replaces it.
 */
export type SignatureMode = "none" | "machine" | "line"

export type DocumentTemplate = {
  id: string
  name: string
  title: string
  body: string
  include_letterhead: boolean
  include_footer: boolean
  verifiable: boolean
  signature_mode: SignatureMode
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

/**
 * A ready-made wording. `caveat` travels with it and is shown next to the
 * text — a draft handed over without saying what to check looks finished.
 */
export type StarterTemplate = {
  key: string
  name: string
  title: string
  body: string
  caveat: string
  include_letterhead: boolean
  include_footer: boolean
  verifiable: boolean
  signature_mode: SignatureMode
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
