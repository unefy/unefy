"use server"

import { revalidatePath } from "next/cache"
import { z } from "zod"

import { apiCall, ApiError } from "@/lib/api"
import type { AudiencePreview, Message } from "@/lib/types/message"

/**
 * Composing and sending a round mail.
 *
 * All three fit in a JSON body — the text of a club letter is kilobytes, not
 * megabytes — so unlike the invoice upload none of this needs a route handler.
 */

export type ActionResult<T = unknown> =
  { success: true; data?: T } | { success: false; error: string }

function toError<T>(error: unknown): ActionResult<T> {
  if (error instanceof ApiError) {
    // The installation is holding member mail back. Its own message, because
    // "reaches nobody" would send the board into the consents rather than
    // into the settings, which is where the switch is.
    if (error.code === "EMAIL_HELD_BACK") {
      return { success: false, error: "heldBack" }
    }
    if (error.status === 403) return { success: false, error: "forbidden" }
    if (error.status === 404) return { success: false, error: "notFound" }
    if (error.status === 422) return { success: false, error: "validation" }
    return { success: false, error: "unknown" }
  }
  return { success: false, error: "unreachable" }
}

const MESSAGES_PATH = "/messages"

const audienceSchema = z.discriminatedUnion("type", [
  z.object({ type: z.literal("all") }),
  z.object({ type: z.literal("function"), id: z.string().uuid() }),
  z.object({
    type: z.literal("event"),
    id: z.string().uuid(),
    include_waitlist: z.boolean(),
  }),
  z.object({
    type: z.literal("debtors"),
    year: z.number().int().min(2000).max(2100),
  }),
])

const kindSchema = z.enum(["notice", "newsletter"])

const composeSchema = z.object({
  kind: kindSchema,
  subject: z.string().trim().min(1).max(255),
  body: z.string().trim().min(1).max(20000),
  audience: audienceSchema,
})

/**
 * Who this would reach, before anything is written.
 *
 * The same resolution the sending does, so the number here is the number that
 * goes out — including the rows the installation holds back.
 */
export async function previewAudienceAction(input: {
  kind: string
  audience: unknown
}): Promise<ActionResult<AudiencePreview>> {
  const parsed = z
    .object({ kind: kindSchema, audience: audienceSchema })
    .safeParse(input)
  if (!parsed.success) return { success: false, error: "validation" }

  try {
    const data = await apiCall<AudiencePreview>("/api/v1/messages/preview", {
      method: "POST",
      body: JSON.stringify(parsed.data),
    })
    return { success: true, data }
  } catch (error) {
    return toError(error)
  }
}

export async function sendTestMessageAction(input: {
  subject: string
  body: string
  to: string
}): Promise<ActionResult<{ delivered: boolean }>> {
  const parsed = z
    .object({
      subject: z.string().trim().min(1).max(255),
      body: z.string().trim().min(1).max(20000),
      to: z.string().trim().email(),
    })
    .safeParse(input)
  if (!parsed.success) return { success: false, error: "validation" }

  try {
    const data = await apiCall<{ delivered: boolean }>(
      "/api/v1/messages/test",
      { method: "POST", body: JSON.stringify(parsed.data) }
    )
    return { success: true, data }
  } catch (error) {
    return toError(error)
  }
}

/** Queue it. The sending itself happens in the background, in batches. */
export async function queueMessageAction(
  input: unknown
): Promise<ActionResult<Message>> {
  const parsed = composeSchema.safeParse(input)
  if (!parsed.success) return { success: false, error: "validation" }

  try {
    const data = await apiCall<Message>("/api/v1/messages", {
      method: "POST",
      body: JSON.stringify(parsed.data),
    })
    revalidatePath(MESSAGES_PATH)
    return { success: true, data }
  } catch (error) {
    return toError(error)
  }
}
