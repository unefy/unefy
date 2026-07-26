"use client"

import { useTranslations } from "next-intl"
import { PageHeader } from "@/components/layout/page-header"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { EventCreateDialog } from "@/components/events/event-create-dialog"
import { EventsTable } from "@/components/events/events-table"

export function EventsView() {
  const t = useTranslations("events")

  return (
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
          <EventsTable scope="upcoming" />
        </TabsContent>
        <TabsContent value="past" className="pt-4">
          <EventsTable scope="past" />
        </TabsContent>
      </Tabs>
    </div>
  )
}
