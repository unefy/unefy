"use client"

import { useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"
import { toast } from "sonner"

import { createEntryAction, deleteEntryAction } from "@/actions/competitions"
import { MemberSearch } from "@/components/attendance/member-search"
import { formatScore } from "@/components/competitions/scoreboard-table"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ConfirmAction } from "@/components/ui/confirm-action"
import { DataTable, type DataTableColumn } from "@/components/ui/data-table"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import type { CompetitionEntry } from "@/lib/types/competition"
import type { Member } from "@/lib/types/member"
import { ScanLineIcon, Trash2Icon } from "lucide-react"

/**
 * The results of one round.
 *
 * Entering a score is two fields — who, and how much — so it is an inline row
 * rather than a dialog: whoever keeps the score enters a dozen of these in a
 * row and should not have to open and close a modal each time.
 */
export function EntriesPanel({
  competitionId,
  sessionId,
  entries,
  memberNames,
  scoreUnit,
  canManage,
  canDelete,
}: {
  competitionId: string
  sessionId: string
  entries: CompetitionEntry[]
  /** member_id → name, resolved by the page. */
  memberNames: Record<string, string>
  scoreUnit: string
  canManage: boolean
  canDelete: boolean
}) {
  const t = useTranslations("competitions.entries")
  const tc = useTranslations("competitions")
  const ts = useTranslations("attendance.search")
  const locale = useLocale()
  const router = useRouter()

  const [member, setMember] = useState<Member | null>(null)
  const [score, setScore] = useState("")
  const [pending, startTransition] = useTransition()

  function add(formData: FormData) {
    startTransition(async () => {
      const result = await createEntryAction(
        competitionId,
        sessionId,
        scoreUnit,
        undefined,
        formData
      )
      if (result.success) {
        toast.success(t("addedToast"))
        setMember(null)
        setScore("")
        router.refresh()
      } else {
        toast.error(tc(`errors.${result.error}`))
      }
    })
  }

  const columns: DataTableColumn<CompetitionEntry>[] = [
    {
      key: "member",
      header: t("columns.member"),
      sortValue: (row) => memberNames[row.member_id],
      cell: (row) => (
        <span className="font-medium">
          {memberNames[row.member_id] ?? "—"}
        </span>
      ),
    },
    {
      key: "score",
      header: `${t("columns.score")} (${scoreUnit})`,
      align: "right",
      shrink: true,
      sortValue: (row) => row.score_value,
      cellClassName: "tabular-nums font-medium",
      cell: (row) => formatScore(row.score_value, locale),
    },
    {
      key: "discipline",
      header: t("columns.discipline"),
      shrink: true,
      sortValue: (row) => row.discipline,
      cellClassName: "text-muted-foreground",
      cell: (row) => row.discipline ?? "—",
    },
    {
      key: "source",
      header: t("columns.source"),
      shrink: true,
      sortValue: (row) => row.source,
      cell: (row) =>
        row.source === "scan" ? (
          <Badge variant="outline" className="gap-1">
            <ScanLineIcon className="size-3" />
            {t("sources.scan")}
          </Badge>
        ) : (
          <span className="text-muted-foreground">{t("sources.manual")}</span>
        ),
    },
    {
      key: "notes",
      header: t("columns.notes"),
      wrap: true,
      sortValue: (row) => row.notes,
      cellClassName: "text-muted-foreground",
      cell: (row) => row.notes ?? "—",
    },
  ]

  if (canDelete) {
    columns.push({
      key: "actions",
      header: "",
      align: "right",
      shrink: true,
      cell: (row) => (
        <ConfirmAction
          trigger={
            <Button variant="ghost" size="sm" aria-label={t("remove")}>
              <Trash2Icon className="text-destructive" />
            </Button>
          }
          title={t("deleteDialog.title")}
          description={t("deleteDialog.description")}
          confirmLabel={t("deleteDialog.confirm")}
          successMessage={t("removedToast")}
          action={deleteEntryAction.bind(
            null,
            competitionId,
            sessionId,
            row.id
          )}
        />
      ),
    })
  }

  return (
    <div className="space-y-3">
      {canManage && (
        <form
          action={add}
          className="flex flex-wrap items-end gap-3 rounded-md border p-3"
        >
          <div className="space-y-2">
            <Label>{t("columns.member")}</Label>
            {member ? (
              <div className="flex h-9 items-center gap-2 rounded-md border px-3">
                <span className="text-sm">
                  {member.first_name} {member.last_name}
                </span>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setMember(null)}
                >
                  {t("clear")}
                </Button>
              </div>
            ) : (
              <MemberSearch
                placeholder={ts("placeholder")}
                actionLabel={t("choose")}
                disabled={pending}
                onSelect={setMember}
              />
            )}
            <input type="hidden" name="member_id" value={member?.id ?? ""} />
          </div>

          <div className="space-y-2">
            <Label htmlFor="score_value">
              {t("columns.score")} ({scoreUnit})
            </Label>
            <Input
              id="score_value"
              name="score_value"
              inputMode="decimal"
              className="w-32"
              value={score}
              onChange={(event) => setScore(event.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="entry_discipline">{t("columns.discipline")}</Label>
            <Input
              id="entry_discipline"
              name="discipline"
              className="w-40"
              maxLength={100}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="entry_notes">{t("columns.notes")}</Label>
            <Input id="entry_notes" name="notes" maxLength={5000} />
          </div>

          <Button type="submit" disabled={pending || !member || score === ""}>
            {pending ? t("saving") : t("add")}
          </Button>
        </form>
      )}

      <DataTable
        data={entries}
        columns={columns}
        rowKey={(row) => row.id}
        searchPlaceholder={t("searchPlaceholder")}
        searchFields={(row) => [memberNames[row.member_id], row.notes]}
        defaultSort={{ key: "score", direction: "desc" }}
        emptyText={t("empty")}
        locale={locale}
      />
    </div>
  )
}
