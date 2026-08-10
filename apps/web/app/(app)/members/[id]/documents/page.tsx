import { getTranslations } from "next-intl/server"

import { MemberDocuments } from "@/components/members/member-documents"
import { listIssuedDocuments, listTemplates } from "@/lib/documents"

/** Certificates for this member: what to issue, and what already went out. */
export default async function MemberDocumentsPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  await getTranslations("documents")

  // Only active templates here: an inactive one cannot be issued, and
  // offering it would produce a refusal the board cannot act on.
  const [templates, documents] = await Promise.all([
    listTemplates().catch(() => []),
    listIssuedDocuments(id).catch(() => []),
  ])

  return (
    <MemberDocuments
      memberId={id}
      templates={templates}
      documents={documents}
    />
  )
}
