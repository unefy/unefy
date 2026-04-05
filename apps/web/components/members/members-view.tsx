"use client"

import { useEffect, useState } from "react"
import { useTranslations } from "next-intl"
import { MembersTable } from "@/components/members/members-table"
import { MemberCreateDialog } from "@/components/members/member-create-dialog"
import { MemberPanel } from "@/components/members/member-panel"
import { PageHeader } from "@/components/layout/page-header"

export function MembersView() {
  const t = useTranslations("members")
  const [selectedId, setSelectedId] = useState<string | null>(null)

  useEffect(() => {
    if (!selectedId) return
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setSelectedId(null)
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [selectedId])

  return (
    <>
      <div className={selectedId ? "mr-[400px]" : ""}>
        <div className="space-y-6">
          <PageHeader title={t("title")} description={t("description")}>
            <MemberCreateDialog />
          </PageHeader>
          <MembersTable selectedId={selectedId} onSelect={setSelectedId} />
        </div>
      </div>

      {selectedId && (
        <MemberPanel
          memberId={selectedId}
          onClose={() => setSelectedId(null)}
        />
      )}
    </>
  )
}
