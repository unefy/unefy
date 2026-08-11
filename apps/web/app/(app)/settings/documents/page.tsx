import Link from "next/link"
import { getTranslations } from "next-intl/server"

import { StarterTemplates } from "@/components/settings/starter-templates"
import { TemplatesTable } from "@/components/settings/templates-table"
import { buttonVariants } from "@/components/ui/button"
import { listStarterTemplates, listTemplates } from "@/lib/documents"
import { PlusIcon } from "lucide-react"

/** The club's own wording for the documents it hands out. */
export default async function TemplatesPage() {
  const [t, templates, starters] = await Promise.all([
    getTranslations("documents"),
    listTemplates(true).catch(() => []),
    // Only owners and admins may read these; a board member simply sees no
    // suggestions rather than an error.
    listStarterTemplates().catch(() => []),
  ])

  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">
            {t("title")}
          </h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            {t("description")}
          </p>
        </div>
        <Link
          href="/settings/documents/new"
          className={buttonVariants({ size: "sm" })}
        >
          <PlusIcon />
          {t("new")}
        </Link>
      </div>

      <TemplatesTable templates={templates} />

      <StarterTemplates starters={starters} />
    </>
  )
}
