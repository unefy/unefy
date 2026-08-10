import { getTranslations } from "next-intl/server"

import { TemplateEditor } from "@/components/settings/template-editor"
import { listVariables } from "@/lib/documents"

export default async function NewTemplatePage() {
  const [t, variables] = await Promise.all([
    getTranslations("documents"),
    listVariables().catch(() => []),
  ])

  return (
    <>
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">{t("new")}</h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          {t("editorHint")}
        </p>
      </div>
      <TemplateEditor template={null} variables={variables} />
    </>
  )
}
