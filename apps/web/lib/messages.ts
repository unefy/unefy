import { apiCall, apiList } from "@/lib/api"
import type { Message, MessageRecipient } from "@/lib/types/message"

/**
 * Server-side readers for the club's round mail.
 *
 * Board and above throughout — what the club sent to whom is committee
 * business, and a member's own copy is in their inbox.
 */

export const MESSAGES_PAGE_SIZE = 50

export async function listMessages(page = 1) {
  return apiList<Message>(
    `/api/v1/messages?page=${page}&per_page=${MESSAGES_PAGE_SIZE}`
  )
}

export async function getMessage(id: string) {
  return apiCall<Message>(`/api/v1/messages/${id}`)
}

/** The rows, filterable — the screen for "who did not get it and why". */
export async function listRecipients(
  id: string,
  options: { status?: string; page?: number } = {}
) {
  const params = new URLSearchParams({
    page: String(options.page ?? 1),
    per_page: "200",
  })
  if (options.status) params.set("status", options.status)
  return apiList<MessageRecipient>(
    `/api/v1/messages/${id}/recipients?${params}`
  )
}
