"use client"

import { useTransition } from "react"
import { useLocale, useTranslations } from "next-intl"
import { toast } from "sonner"

import {
  revokeInvitationAction,
  setAccessActiveAction,
  setAccessRoleAction,
} from "@/actions/club-access"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { DataTable, type DataTableColumn } from "@/components/ui/data-table"
import { DateCell } from "@/components/ui/date-cell"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { ROLE_KEYS, roleLabel } from "@/lib/labels"
import type { ClubAccess } from "@/lib/types/member"

export function ClubAccessTables({ access }: { access: ClubAccess }) {
  const t = useTranslations("clubAccess")
  const tl = useTranslations("admin")
  const locale = useLocale()
  const [pending, startTransition] = useTransition()

  function run(
    action: () => Promise<{ success: boolean; error?: string }>,
    successMessage: string
  ) {
    startTransition(async () => {
      const result = await action()
      if (result.success) {
        toast.success(successMessage)
      } else {
        toast.error(t(`errors.${result.error ?? "unknown"}`))
      }
    })
  }

  const memberColumns: DataTableColumn<ClubAccess["members"][number]>[] = [
    {
      key: "name",
      header: t("columns.name"),
      sortValue: (row) => row.name,
      cell: (row) => <span className="font-medium">{row.name}</span>,
    },
    {
      key: "email",
      header: t("columns.email"),
      sortValue: (row) => row.email,
      cellClassName: "text-muted-foreground",
      cell: (row) => row.email,
    },
    {
      key: "role",
      header: t("columns.role"),
      shrink: true,
      sortValue: (row) => roleLabel(tl, row.role),
      // Editable in place: changing a role is the most frequent action here,
      // and a dialog per row would add a step without adding clarity.
      cell: (row) => (
        <Select
          value={row.role}
          onValueChange={(value) =>
            run(
              () => setAccessRoleAction(row.user_id, String(value)),
              t("roleChanged")
            )
          }
        >
          <SelectTrigger size="sm" className="w-40">
            <SelectValue>{(value: string) => roleLabel(tl, value)}</SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {ROLE_KEYS.map((key) => (
                <SelectItem key={key} value={key}>
                  {roleLabel(tl, key)}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
      ),
    },
    {
      key: "status",
      header: t("columns.status"),
      sortValue: (row) => row.is_active,
      cell: (row) => (
        <Badge variant={row.is_active ? "secondary" : "destructive"}>
          {row.is_active ? t("active") : t("blocked")}
        </Badge>
      ),
    },
    {
      key: "joinedAt",
      header: t("columns.joinedAt"),
      shrink: true,
      sortValue: (row) => row.joined_at,
      cellClassName: "text-muted-foreground",
      cell: (row) => <DateCell value={row.joined_at} />,
    },
    {
      key: "actions",
      header: "",
      align: "right",
      shrink: true,
      cell: (row) => (
        <Button
          variant="outline"
          size="sm"
          disabled={pending}
          onClick={() =>
            run(
              () => setAccessActiveAction(row.user_id, !row.is_active),
              row.is_active ? t("blockedToast") : t("unblockedToast")
            )
          }
        >
          {row.is_active ? t("block") : t("unblock")}
        </Button>
      ),
    },
  ]

  const inviteColumns: DataTableColumn<ClubAccess["invitations"][number]>[] = [
    {
      key: "email",
      header: t("inviteColumns.email"),
      sortValue: (row) => row.email,
      cell: (row) => <span className="font-medium">{row.email}</span>,
    },
    {
      key: "role",
      header: t("inviteColumns.role"),
      sortValue: (row) => roleLabel(tl, row.role),
      cell: (row) => <Badge variant="outline">{roleLabel(tl, row.role)}</Badge>,
    },
    {
      key: "expiresAt",
      header: t("inviteColumns.expiresAt"),
      shrink: true,
      sortValue: (row) => row.expires_at,
      cell: (row) =>
        row.is_expired ? (
          <Badge variant="destructive">{t("expired")}</Badge>
        ) : (
          <DateCell value={row.expires_at} />
        ),
    },
    {
      key: "createdAt",
      header: t("inviteColumns.createdAt"),
      shrink: true,
      sortValue: (row) => row.created_at,
      cellClassName: "text-muted-foreground",
      cell: (row) => <DateCell value={row.created_at} />,
    },
    {
      key: "actions",
      header: "",
      align: "right",
      shrink: true,
      cell: (row) => (
        <Button
          variant="outline"
          size="sm"
          disabled={pending}
          onClick={() =>
            run(() => revokeInvitationAction(row.id), t("revokedToast"))
          }
        >
          {t("revoke")}
        </Button>
      ),
    },
  ]

  return (
    <>
      <section className="space-y-3">
        <h2 className="text-sm font-medium text-muted-foreground">
          {t("members")}
        </h2>
        <DataTable
          data={access.members}
          columns={memberColumns}
          rowKey={(row) => row.user_id}
          locale={locale}
          defaultSort={{ key: "name", direction: "asc" }}
          searchPlaceholder={t("searchPlaceholder")}
          searchFields={(row) => [row.name, row.email]}
          emptyText={t("noMembers")}
        />
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-medium text-muted-foreground">
          {t("invitations")}
        </h2>
        <DataTable
          data={access.invitations}
          columns={inviteColumns}
          rowKey={(row) => row.id}
          locale={locale}
          defaultSort={{ key: "createdAt", direction: "desc" }}
          emptyText={t("noInvitations")}
        />
      </section>
    </>
  )
}
