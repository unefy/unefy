"use client"

import { useTranslations } from "next-intl"

import { buttonVariants } from "@/components/ui/button"
import { DownloadIcon } from "lucide-react"

/**
 * The Art. 15 download.
 *
 * A plain link, not a fetch: the browser's own download handling is better
 * than anything reimplemented here, and the route sets the filename.
 */
export function MemberExport({ memberId }: { memberId?: string }) {
  const t = useTranslations("consents")
  const href = memberId
    ? `/api/members/export?member=${encodeURIComponent(memberId)}`
    : "/api/members/export"

  return (
    <a
      href={href}
      download
      className={buttonVariants({ variant: "outline", size: "sm" })}
    >
      <DownloadIcon />
      {t("export.action")}
    </a>
  )
}
