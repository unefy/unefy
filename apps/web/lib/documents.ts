import { apiCall } from "@/lib/api"
import type {
  DocumentTemplate,
  DocumentVariable,
  IssuedDocument,
  StarterTemplate,
} from "@/lib/types/document"

/** The club's templates. Inactive ones only when asked for. */
export async function listTemplates(includeInactive = false) {
  const query = includeInactive ? "?include_inactive=true" : ""
  return apiCall<DocumentTemplate[]>(`/api/v1/documents/templates${query}`)
}

export async function getTemplate(id: string) {
  return apiCall<DocumentTemplate>(`/api/v1/documents/templates/${id}`)
}

/** The placeholder catalogue — the same one that validates a save. */
export async function listVariables() {
  return apiCall<DocumentVariable[]>("/api/v1/documents/variables")
}

/** Ready-made wordings to start from. Drafts — nothing is installed by us. */
export async function listStarterTemplates() {
  return apiCall<StarterTemplate[]>("/api/v1/documents/starter-templates")
}

/** What the club has issued, optionally for one member. */
export async function listIssuedDocuments(memberId?: string) {
  const query = memberId ? `?member_id=${encodeURIComponent(memberId)}` : ""
  return apiCall<IssuedDocument[]>(`/api/v1/documents${query}`)
}
