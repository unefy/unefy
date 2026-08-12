import { apiCall, apiList } from "@/lib/api"
import type {
  LibraryDocument,
  LibraryFolder,
  LibraryUsage,
} from "@/lib/types/library"

/** The club's whole folder tree, flat. Small enough to send in one piece. */
export async function listFolders() {
  return apiCall<LibraryFolder[]>("/api/v1/library/folders")
}

/**
 * One folder's contents — or the whole club when searching.
 *
 * `folderId: null` is the root, which is not the same as "everything": the
 * library is a filing cabinet, and opening it shows the top drawer.
 */
export async function listDocuments({
  folderId,
  search,
  page = 1,
}: {
  folderId?: string | null
  search?: string
  page?: number
} = {}) {
  const params = new URLSearchParams({ page: String(page), per_page: "100" })
  if (folderId) params.set("folder_id", folderId)
  if (search) params.set("search", search)
  return apiList<LibraryDocument>(`/api/v1/library/documents?${params}`)
}

/** This version and everything it replaced, newest first. */
export async function listVersions(documentId: string) {
  return apiCall<LibraryDocument[]>(
    `/api/v1/library/documents/${documentId}/versions`
  )
}

/** What the club has used, and what it may use. */
export async function getUsage() {
  return apiCall<LibraryUsage>("/api/v1/library/usage")
}
