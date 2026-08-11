"use server"

import { revalidatePath } from "next/cache"
import { z } from "zod"

import { API_BASE, apiCall, ApiError } from "@/lib/api"
import type { ActionResult } from "@/actions/members"
import type {
  DocumentTemplate,
  IssuedDocument,
  SignatureLink,
  SigningPage,
  TemplatePreview,
} from "@/lib/types/document"

function toError<T>(error: unknown): ActionResult<T> {
  if (error instanceof ApiError) {
    if (error.status === 409) return { success: false, error: "conflict" }
    if (error.status === 403) return { success: false, error: "forbidden" }
    if (error.status === 404) return { success: false, error: "notFound" }
    // A template naming a placeholder that does not exist lands here. The
    // editor marks the names itself from the preview, so the toast only has
    // to say that something is wrong, not what.
    if (error.status === 422) return { success: false, error: "validation" }
    return { success: false, error: "unknown" }
  }
  return { success: false, error: "unreachable" }
}

const templateSchema = z.object({
  name: z.string().trim().min(1).max(255),
  title: z.string().trim().min(1).max(255),
  body: z.string().min(1).max(20000),
  include_letterhead: z.boolean(),
  include_footer: z.boolean(),
  verifiable: z.boolean(),
  signature_mode: z.enum(["none", "machine", "line"]),
  is_active: z.boolean(),
})

export type TemplateInput = z.infer<typeof templateSchema>

export async function saveTemplateAction(
  templateId: string | null,
  input: TemplateInput
): Promise<ActionResult<DocumentTemplate>> {
  const parsed = templateSchema.safeParse(input)
  if (!parsed.success) return { success: false, error: "validation" }
  if (templateId !== null && !z.string().uuid().safeParse(templateId).success) {
    return { success: false, error: "validation" }
  }

  try {
    const template = await apiCall<DocumentTemplate>(
      templateId
        ? `/api/v1/documents/templates/${templateId}`
        : "/api/v1/documents/templates",
      {
        method: templateId ? "PATCH" : "POST",
        body: JSON.stringify(parsed.data),
      }
    )
    revalidatePath("/settings/documents")
    return { success: true, data: template }
  } catch (error) {
    return toError(error)
  }
}

/**
 * Ask for a link that lets somebody sign this document on their own phone.
 *
 * Requested per document and per attempt: the link is the whole
 * authorisation, so it should exist only while somebody is standing there
 * meaning to sign. It expires by itself and is spent on signing.
 */
export async function requestSignatureLinkAction(
  documentId: string
): Promise<ActionResult<SignatureLink>> {
  if (!z.string().uuid().safeParse(documentId).success) {
    return { success: false, error: "validation" }
  }
  try {
    const link = await apiCall<SignatureLink>(
      `/api/v1/documents/${documentId}/signature-link`,
      { method: "POST" }
    )
    return { success: true, data: link }
  } catch (error) {
    return toError(error)
  }
}

/**
 * What the signing page shows, fetched without a session.
 *
 * Deliberately not `apiCall`: the person signing is on their own phone and
 * has no session here, and forwarding somebody else's would be wrong even if
 * one existed.
 */
export async function signingPageQuery(
  token: string
): Promise<SigningPage | null> {
  try {
    const response = await fetch(
      `${API_BASE}/sign/${encodeURIComponent(token)}`,
      { cache: "no-store" }
    )
    if (!response.ok) return null
    return ((await response.json()) as { data: SigningPage }).data
  } catch {
    return null
  }
}

export async function submitSignatureAction(
  token: string,
  signaturePng: string
): Promise<ActionResult> {
  if (!signaturePng.startsWith("data:image/png;base64,")) {
    return { success: false, error: "validation" }
  }
  try {
    const response = await fetch(
      `${API_BASE}/sign/${encodeURIComponent(token)}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ signature_png: signaturePng }),
        cache: "no-store",
      }
    )
    if (response.status === 429) return { success: false, error: "rateLimited" }
    if (response.status === 404) return { success: false, error: "notFound" }
    if (!response.ok) return { success: false, error: "unknown" }
    return { success: true }
  } catch {
    return { success: false, error: "unreachable" }
  }
}

export async function deleteTemplateAction(
  templateId: string
): Promise<ActionResult> {
  if (!z.string().uuid().safeParse(templateId).success) {
    return { success: false, error: "validation" }
  }

  try {
    await apiCall(`/api/v1/documents/templates/${templateId}`, {
      method: "DELETE",
    })
    revalidatePath("/settings/documents")
    return { success: true }
  } catch (error) {
    return toError(error)
  }
}

/**
 * Renders a draft against stand-in values.
 *
 * Runs on every pause in typing, so it stays a read: it writes nothing and
 * revalidates nothing.
 */
export async function previewTemplateAction(
  body: string
): Promise<ActionResult<TemplatePreview>> {
  try {
    const preview = await apiCall<TemplatePreview>(
      "/api/v1/documents/templates/preview",
      { method: "POST", body: JSON.stringify({ body }) }
    )
    return { success: true, data: preview }
  } catch (error) {
    return toError(error)
  }
}

export async function issueDocumentAction(
  memberId: string,
  templateId: string
): Promise<ActionResult<IssuedDocument>> {
  if (
    !z.string().uuid().safeParse(memberId).success ||
    !z.string().uuid().safeParse(templateId).success
  ) {
    return { success: false, error: "validation" }
  }

  try {
    const document = await apiCall<IssuedDocument>(
      `/api/v1/documents/members/${memberId}/issue`,
      { method: "POST", body: JSON.stringify({ template_id: templateId }) }
    )
    revalidatePath(`/members/${memberId}/documents`)
    return { success: true, data: document }
  } catch (error) {
    return toError(error)
  }
}

export async function revokeDocumentAction(
  documentId: string,
  memberId: string,
  reason: string
): Promise<ActionResult> {
  if (!z.string().uuid().safeParse(documentId).success) {
    return { success: false, error: "validation" }
  }
  if (!reason.trim()) return { success: false, error: "validation" }

  try {
    await apiCall(`/api/v1/documents/${documentId}/revoke`, {
      method: "POST",
      body: JSON.stringify({ reason: reason.trim() }),
    })
    revalidatePath(`/members/${memberId}/documents`)
    return { success: true }
  } catch (error) {
    return toError(error)
  }
}
