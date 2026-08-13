/** Mirrors `app/schemas/message.py` and the payloads in `api/v1/messages.py`. */

/**
 * A duty communication or something the club would like to send.
 *
 * `notice` reaches everyone the selection resolves to — the invitation to the
 * general meeting is owed to members who never consented to anything.
 * `newsletter` needs consent. The sender states which it is; deriving it from
 * the text would be guessing at a legal distinction.
 */
export type MessageKind = "notice" | "newsletter"

export type Audience =
  | { type: "all" }
  | { type: "function"; id: string }
  | { type: "event"; id: string; include_waitlist: boolean }
  | { type: "debtors"; year: number }

export type MessageStatus = "queued" | "sending" | "done" | "failed"

export type RecipientStatus = "pending" | "sent" | "failed" | "skipped"

/** Why a row was skipped. `not_asked` is not `refused` — see the summary. */
export type SkipReason =
  "no_email" | "refused" | "not_asked" | "duplicate" | "held_back"

export type Message = {
  id: string
  kind: MessageKind
  subject: string
  body: string
  audience: Audience
  status: MessageStatus
  recipient_count: number
  queued_at: string
  finished_at: string | null
  counts: Record<string, number>
}

export type MessageRecipient = {
  id: string
  member_id: string | null
  email: string | null
  status: RecipientStatus
  reason: SkipReason | null
  error: string | null
  attempts: number
  sent_at: string | null
}

export type RecipientPreview = {
  member_id: string
  first_name: string
  last_name: string
  email: string | null
  status: "pending" | "skipped"
  reason: SkipReason | null
}

export type AudienceSummary = {
  total: number
  pending: number
  skipped_no_email: number
  skipped_refused: number
  skipped_not_asked: number
  /** One address, two members — a couple sharing a mailbox. */
  skipped_duplicate: number
  /** The installation is not sending member mail (`EMAIL_DELIVERY`). */
  skipped_held_back: number
}

export type AudiencePreview = {
  summary: AudienceSummary
  recipients: RecipientPreview[]
  truncated: boolean
}
