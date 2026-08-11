"use client"

import Link from "next/link"
import { useTranslations } from "next-intl"

import type { StarterTemplate } from "@/lib/types/document"
import { FileTextIcon } from "lucide-react"

/**
 * The ready-made wordings, offered as drafts.
 *
 * Cards rather than a one-click install: the caveat belongs in front of the
 * club before the text does, and picking one only opens the editor. Nothing
 * exists until somebody has read it and pressed save.
 */
export function StarterTemplates({
  starters,
}: {
  starters: StarterTemplate[]
}) {
  const t = useTranslations("documents")

  if (starters.length === 0) return null

  return (
    <section className="space-y-3">
      <div className="space-y-1">
        <h2 className="text-sm font-medium">{t("starters.title")}</h2>
        <p className="max-w-3xl text-sm text-muted-foreground">
          {t("starters.description")}
        </p>
      </div>

      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {starters.map((starter) => (
          <li key={starter.key}>
            <Link
              href={`/settings/documents/new?starter=${encodeURIComponent(starter.key)}`}
              className="flex h-full flex-col gap-2 rounded-lg border p-4 transition-colors hover:bg-accent/50"
            >
              <span className="flex items-center gap-2 text-sm font-medium">
                <FileTextIcon className="size-4 text-muted-foreground" />
                {starter.name}
              </span>
              <span className="line-clamp-3 text-xs text-muted-foreground">
                {starter.caveat}
              </span>
            </Link>
          </li>
        ))}
      </ul>

      <p className="max-w-3xl text-xs text-muted-foreground">
        {t("starters.disclaimer")}
      </p>
    </section>
  )
}
