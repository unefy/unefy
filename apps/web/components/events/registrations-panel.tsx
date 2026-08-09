"use client"

import { useTransition } from "react"
import { useRouter } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"
import { toast } from "sonner"

import { registerMemberAction, removeRegistrationAction } from "@/actions/events"
import { MemberSearch } from "@/components/attendance/member-search"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { DataTable, type DataTableColumn } from "@/components/ui/data-table"
import { formatDateTime } from "@/lib/time"
import type { EventRegistration } from "@/lib/types/event"
import { Trash2Icon } from "lucide-react"

/**
 * Who is on the event, and the board's way to add or remove someone.
 *
 * Waitlisted rows stay in the same table rather than in a second list: the
 * order is what makes a waiting list readable, and splitting it hides who moves
 * up next.
 */
export function RegistrationsPanel({
  eventId,
  registrations,
  timeZone,
  canManage,
}: {
  eventId: string
  registrations: EventRegistration[]
  timeZone: string
  canManage: boolean
}) {
  const t = useTranslations("events.registrations")
  const ts = useTranslations("attendance.search")
  const locale = useLocale()
  const router = useRouter()
  const [pending, startTransition] = useTransition()

  function add(memberId: string) {
    startTransition(async () => {
      const result = await registerMemberAction(eventId, memberId)
      if (result.success) {
        toast.success(t("addedToast"))
        router.refresh()
      } else {
        toast.error(t(`errors.${result.error}`))
      }
    })
  }

  function remove(registrationId: string) {
    startTransition(async () => {
      const result = await removeRegistrationAction(eventId, registrationId)
      if (result.success) {
        toast.success(t("removedToast"))
        router.refresh()
      } else {
        toast.error(t(`errors.${result.error}`))
      }
    })
  }

  const columns: DataTableColumn<EventRegistration>[] = [
    {
      key: "name",
      header: t("columns.member"),
      sortValue: (row) => row.member_name,
      cell: (row) => (
        <span className="font-medium">{row.member_name ?? "—"}</span>
      ),
    },
    {
      key: "status",
      header: t("columns.status"),
      shrink: true,
      sortValue: (row) => row.status,
      cell: (row) => (
        <Badge
          variant={row.status === "registered" ? "secondary" : "outline"}
        >
          {t(`status.${row.status}`)}
        </Badge>
      ),
    },
    {
      key: "createdAt",
      header: t("columns.registeredAt"),
      shrink: true,
      sortValue: (row) => row.created_at,
      cellClassName: "text-muted-foreground",
      cell: (row) => formatDateTime(row.created_at, locale, timeZone),
    },
  ]

  if (canManage) {
    columns.push({
      key: "actions",
      header: "",
      align: "right",
      shrink: true,
      cell: (row) => (
        <Button
          variant="ghost"
          size="sm"
          disabled={pending}
          aria-label={t("remove")}
          onClick={() => remove(row.id)}
        >
          <Trash2Icon className="text-destructive" />
        </Button>
      ),
    })
  }

  return (
    <div className="space-y-3">
      {canManage && (
        <MemberSearch
          placeholder={ts("placeholder")}
          actionLabel={t("add")}
          disabled={pending}
          takenIds={registrations.map((r) => r.member_id)}
          takenLabel={t("alreadyRegistered")}
          onSelect={(member) => add(member.id)}
        />
      )}
      <DataTable
        data={registrations}
        columns={columns}
        rowKey={(row) => row.id}
        searchPlaceholder={t("searchPlaceholder")}
        searchFields={(row) => [row.member_name]}
        defaultSort={{ key: "createdAt", direction: "asc" }}
        emptyText={t("empty")}
        locale={locale}
      />
    </div>
  )
}
