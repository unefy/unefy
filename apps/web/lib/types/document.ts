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

/** Where to sign, plus the same address as a QR the phone can scan. */
export type SignatureLink = {
  url: string
  expires_in: number
  /** One string of "0"/"1" per row of the QR. Drawn as squares, not an image. */
  qr: string[]
}

/** What the signing page shows the person holding the phone. */
export type SigningPage = {
  club_name: string
  title: string
  body: string
  member_name: string
  issued_on: string
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
  signature_mode: SignatureMode
  /** When it was signed on a device — never the drawing itself. */
  signed_at: string | null
}
