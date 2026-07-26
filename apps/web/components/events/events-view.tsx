"use client"

import { useEffect, useState } from "react"
import { useTranslations } from "next-intl"
import { PageHeader } from "@/components/layout/page-header"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { EventCreateDialog } from "@/components/events/event-create-dialog"
import { EventPanel } from "@/components/events/event-panel"
import { EventsTable } from "@/components/events/events-table"

export function EventsView() {
  const t = useTranslations("events")
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
            <EventCreateDialog />
          </PageHeader>

          <Tabs defaultValue="upcoming">
            <TabsList>
              <TabsTrigger value="upcoming">{t("upcoming")}</TabsTrigger>
              <TabsTrigger value="past">{t("past")}</TabsTrigger>
            </TabsList>
            <TabsContent value="upcoming" className="pt-4">
              <EventsTable
                scope="upcoming"
                selectedId={selectedId}
                onSelect={setSelectedId}
              />
            </TabsContent>
            <TabsContent value="past" className="pt-4">
              <EventsTable
                scope="past"
                selectedId={selectedId}
                onSelect={setSelectedId}
              />
            </TabsContent>
          </Tabs>
        </div>
      </div>

      {selectedId && (
        <EventPanel eventId={selectedId} onClose={() => setSelectedId(null)} />
      )}
    </>
  )
}
