"use server"

import { revalidatePath } from "next/cache"
import { z } from "zod"

import { apiCall, ApiError } from "@/lib/api"
import type { LibraryDocument, LibraryFolder } from "@/lib/types/library"

/**
 * Everything about the library that fits in a JSON body: folders, and the
 * fields around a document.
 *
 * The upload is deliberately *not* here. A server action's body is capped at
 * 1 MB and a scanned protocol is not — it goes through
 * `app/api/library/upload/route.ts`, which streams.
 */

export type ActionResult<T = unknown> =
  | { success: true; data?: T }
  | { success: false; error: string }

function toError<T>(error: unknown): ActionResult<T> {
  if (error instanceof ApiError) {
    if (error.status === 403) return { success: false, error: "forbidden" }
    if (error.status === 404) return { success: false, error: "notFound" }
    if (error.status === 409) return { success: false, error: "conflict" }
    if (error.status === 422) return { success: false, error: "validation" }
    return { success: false, error: "unknown" }
  }
  return { success: false, error: "unreachable" }
}

const LIBRARY_PATH = "/library"

const folderSchema = z.object({
  name: z.string().trim().min(1).max(255),
  parent_id: z.string().uuid().nullable(),
  sort_order: z.number().int(),
})

export async function createFolderAction(
  input: z.input<typeof folderSchema>
): Promise<ActionResult<LibraryFolder>> {
  const parsed = folderSchema.safeParse(input)
  if (!parsed.success) return { success: false, error: "validation" }

  try {
    const created = await apiCall<LibraryFolder>("/api/v1/library/folders", {
      method: "POST",
      body: JSON.stringify(parsed.data),
    })
    revalidatePath(LIBRARY_PATH)
    return { success: true, data: created }
  } catch (error) {
    return toError(error)
  }
}

export async function updateFolderAction(
  folderId: string,
  input: Partial<z.input<typeof folderSchema>>
): Promise<ActionResult<LibraryFolder>> {
  const parsed = folderSchema.partial().safeParse(input)
  if (!parsed.success) return { success: false, error: "validation" }

  try {
    const updated = await apiCall<LibraryFolder>(
      `/api/v1/library/folders/${folderId}`,
      { method: "PATCH", body: JSON.stringify(parsed.data) }
    )
    revalidatePath(LIBRARY_PATH)
    return { success: true, data: updated }
  } catch (error) {
    return toError(error)
  }
}

export async function deleteFolderAction(
  folderId: string
): Promise<ActionResult> {
  try {
    await apiCall(`/api/v1/library/folders/${folderId}`, { method: "DELETE" })
    revalidatePath(LIBRARY_PATH)
    return { success: true }
  } catch (error) {
    return toError(error)
  }
}

const documentSchema = z.object({
  title: z.string().trim().min(1).max(255),
  description: z.string().trim().max(5000).nullable(),
  folder_id: z.string().uuid().nullable(),
  visibility: z.enum(["board", "members"]),
})

export async function updateDocumentAction(
  documentId: string,
  input: Partial<z.input<typeof documentSchema>>
): Promise<ActionResult<LibraryDocument>> {
  const parsed = documentSchema.partial().safeParse(input)
  if (!parsed.success) return { success: false, error: "validation" }

  try {
    const updated = await apiCall<LibraryDocument>(
      `/api/v1/library/documents/${documentId}`,
      { method: "PATCH", body: JSON.stringify(parsed.data) }
    )
    revalidatePath(LIBRARY_PATH)
    return { success: true, data: updated }
  } catch (error) {
    return toError(error)
  }
}

export async function deleteDocumentAction(
  documentId: string
): Promise<ActionResult> {
  try {
    await apiCall(`/api/v1/library/documents/${documentId}`, {
      method: "DELETE",
    })
    revalidatePath(LIBRARY_PATH)
    return { success: true }
  } catch (error) {
    return toError(error)
  }
}
