import { getTranslations } from "next-intl/server"

import { LibraryView } from "@/components/library/library-view"
import { getSession } from "@/lib/auth"
import { listDocuments, listFolders, getUsage } from "@/lib/library"

/** Filing is the committee's; reading is every member's, filtered by
 * visibility in the backend. */
const EDITOR_ROLES = ["owner", "admin", "board"]

export default async function LibraryPage({
  searchParams,
}: {
  searchParams: Promise<{ folder?: string; q?: string }>
}) {
  const [t, { folder, q }, session] = await Promise.all([
    getTranslations("library"),
    searchParams,
    getSession(),
  ])

  const canEdit = EDITOR_ROLES.includes(session?.role ?? "")
  const folderId = folder && /^[0-9a-f-]{36}$/i.test(folder) ? folder : null
  // Searching spans every folder — the drawer stays in the URL so that
  // clearing the box returns to it rather than to the root.
  const search = (q ?? "").slice(0, 200).trim()

  const [folders, documents, usage] = await Promise.all([
    listFolders().catch(() => []),
    listDocuments({ folderId, search: search || undefined })
      .then((page) => page.data)
      .catch(() => []),
    // Only the committee is shown the quota, and only the committee's request
    // should fail quietly if the endpoint is unavailable.
    canEdit ? getUsage().catch(() => null) : Promise.resolve(null),
  ])

  return (
    <>
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          {t("description")}
        </p>
      </div>
      <LibraryView
        folders={folders}
        documents={documents}
        currentFolderId={folderId}
        searchTerm={search}
        usage={usage}
        canEdit={canEdit}
      />
    </>
  )
}
