import { getTranslations } from "next-intl/server"

import { TemplateEditor } from "@/components/settings/template-editor"
import { listStarterTemplates, listVariables } from "@/lib/documents"

/**
 * A new template, optionally starting from one of the ready-made wordings.
 *
 * The starter is resolved here and handed to the editor as ordinary initial
 * values — there is no "install a template" write endpoint, so nothing exists
 * until the club has read the text and pressed save.
 */
export default async function NewTemplatePage({
  searchParams,
}: {
  searchParams: Promise<{ starter?: string }>
}) {
  const [t, { starter: key }] = await Promise.all([
    getTranslations("documents"),
    searchParams,
  ])

  const [variables, starters] = await Promise.all([
    listVariables().catch(() => []),
    key ? listStarterTemplates().catch(() => []) : [],
  ])
  const starter = starters.find((s) => s.key === key) ?? null

  return (
    <>
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">
          {starter ? starter.name : t("new")}
        </h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          {t("editorHint")}
        </p>
      </div>
      <TemplateEditor template={null} variables={variables} starter={starter} />
    </>
  )
}
