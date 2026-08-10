import { notFound } from "next/navigation"
import { getTranslations } from "next-intl/server"

import { TemplateEditor } from "@/components/settings/template-editor"
import { getTemplate, listVariables } from "@/lib/documents"

export default async function EditTemplatePage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const [t, { id }] = await Promise.all([getTranslations("documents"), params])

  const [template, variables] = await Promise.all([
    getTemplate(id).catch(() => null),
    listVariables().catch(() => []),
  ])
  if (!template) notFound()

  return (
    <>
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">
          {template.name}
        </h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          {t("editorHint")}
        </p>
      </div>
      <TemplateEditor template={template} variables={variables} />
    </>
  )
}
