/**
 * The club's filing cabinet — "Ablage" in the UI, `library` in the code.
 *
 * Not to be confused with `lib/types/document.ts`, which is the certificate
 * module: those documents are *produced* from a template, these are files
 * somebody uploaded.
 */

export type LibraryVisibility = "board" | "members"

export type LibraryFolder = {
  id: string
  parent_id: string | null
  name: string
  sort_order: number
  created_at: string
  updated_at: string
}

export type LibraryDocument = {
  id: string
  folder_id: string | null
  title: string
  description: string | null
  visibility: LibraryVisibility
  original_filename: string
  content_type: string
  byte_size: number
  checksum_sha256: string
  uploaded_by_user_id: string | null
  uploaded_at: string
  replaces_id: string | null
  superseded_at: string | null
  created_at: string
  updated_at: string
}

export type LibraryUsage = {
  used_bytes: number
  quota_bytes: number
  max_upload_bytes: number
}
