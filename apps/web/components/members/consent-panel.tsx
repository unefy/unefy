"use client"

import { useRouter } from "next/navigation"
import { useState, useTransition } from "react"
import { useLocale, useTranslations } from "next-intl"
import { toast } from "sonner"

import {
  recordMemberConsentAction,
  recordOwnConsentAction,
} from "@/actions/consents"
import { Badge } from "@/components/ui/badge"
import { DateCell } from "@/components/ui/date-cell"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { DataTable, type DataTableColumn } from "@/components/ui/data-table"
import type {
  ConsentEntry,
  ConsentKind,
  ConsentOverview,
} from "@/lib/types/consent"

const KINDS: ConsentKind[] = ["photos", "newsletter", "directory"]

/**
 * What a member allows, and how it came about.
 *
 * The history is shown, not hidden behind a detail view: the trail is the
 * reason the ledger exists, and a club that cannot see when it asked cannot
 * prove anything with it.
 *
 * `memberId` absent means the member is looking at their own — the writes then
 * go through the self-service action and carry no date field, because somebody
 * answering in their own account answers now.
 */
export function ConsentPanel({
  overview,
  memberId,
  canEdit = true,
}: {
  overview: ConsentOverview
  memberId?: string
  canEdit?: boolean
}) {
  const t = useTranslations("consents")
  const locale = useLocale()
  const router = useRouter()
  const [pending, startTransition] = useTransition()
  const [recordedAt, setRecordedAt] = useState("")
  const [note, setNote] = useState("")

  const byKind = new Map(overview.current.map((c) => [c.kind, c]))

  const columns: DataTableColumn<ConsentEntry>[] = [
    {
      key: "kind",
      header: t("columns.kind"),
      cell: (row) => t(`kinds.${row.kind}.label`),
      sortValue: (row) => row.kind,
    },
    {
      key: "granted",
      header: t("columns.answer"),
      cell: (row) => (
        <Badge variant={row.granted ? "default" : "outline"}>
          {row.granted ? t("yes") : t("no")}
        </Badge>
      ),
      sortValue: (row) => row.granted,
      shrink: true,
    },
    {
      key: "recorded_at",
      header: t("columns.when"),
      cell: (row) => <DateCell value={row.recorded_at} />,
      sortValue: (row) => row.recorded_at,
      shrink: true,
    },
    {
      key: "source",
      header: t("columns.source"),
      cell: (row) => t(`sources.${row.source}`),
      sortValue: (row) => row.source,
      shrink: true,
    },
    {
      key: "note",
      header: t("columns.note"),
      cell: (row) => (
        <span className="text-muted-foreground">{row.note ?? "—"}</span>
      ),
      wrap: true,
    },
  ]

  function toggle(kind: ConsentKind, granted: boolean) {
    startTransition(async () => {
      const result = memberId
        ? await recordMemberConsentAction(memberId, kind, granted, {
            recordedAt,
            note,
          })
        : await recordOwnConsentAction(kind, granted)

      if (!result.success) {
        toast.error(t(`errors.${result.error}`))
        return
      }
      toast.success(granted ? t("granted") : t("withdrawn"))
      setNote("")
      router.refresh()
    })
  }

  return (
    <div className="space-y-6">
      <section className="space-y-4 rounded-lg border p-4">
        <div className="space-y-1">
          <h2 className="text-sm font-medium">{t("current")}</h2>
          <p className="text-sm text-muted-foreground">{t("intro")}</p>
        </div>

        <div className="space-y-4">
          {KINDS.map((kind) => {
            const state = byKind.get(kind)
            const granted = state?.granted ?? false
            return (
              <div
                key={kind}
                className="flex flex-wrap items-start justify-between gap-3 border-b pb-4 last:border-0 last:pb-0"
              >
                <div className="space-y-1">
                  <Label
                    htmlFor={`consent-${kind}`}
                    className="text-sm font-medium"
                  >
                    {t(`kinds.${kind}.label`)}
                  </Label>
                  <p className="max-w-xl text-sm text-muted-foreground">
                    {t(`kinds.${kind}.description`)}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {state?.granted === null || state === undefined ? (
                      // Never asked is its own state. Showing it as "no" would
                      // claim the club put a question it never put.
                      t("neverAsked")
                    ) : (
                      <>
                        {t(`sources.${state.source}`)} ·{" "}
                        <DateCell value={state.since} />
                      </>
                    )}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <Switch
                    id={`consent-${kind}`}
                    checked={granted}
                    disabled={!canEdit || pending}
                    onCheckedChange={(checked) =>
                      toggle(kind, checked === true)
                    }
                  />
                  <span className="w-16 text-sm text-muted-foreground">
                    {state?.granted === null || state === undefined
                      ? "—"
                      : granted
                        ? t("yes")
                        : t("no")}
                  </span>
                </div>
              </div>
            )
          })}
        </div>

        {canEdit && memberId ? (
          <div className="grid gap-3 rounded-lg bg-muted/40 p-3 sm:grid-cols-2">
            <p className="text-xs text-muted-foreground sm:col-span-2">
              {t("backdateHint")}
            </p>
            <div className="space-y-1.5">
              <Label htmlFor="consent-date" className="text-xs">
                {t("recordedAt")}
              </Label>
              <Input
                id="consent-date"
                type="date"
                value={recordedAt}
                onChange={(event) => setRecordedAt(event.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="consent-note" className="text-xs">
                {t("note")}
              </Label>
              <Input
                id="consent-note"
                value={note}
                maxLength={1000}
                onChange={(event) => setNote(event.target.value)}
                placeholder={t("notePlaceholder")}
              />
            </div>
          </div>
        ) : null}
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-medium">{t("history")}</h2>
        <DataTable
          data={overview.history}
          columns={columns}
          rowKey={(row) => row.id}
          defaultSort={{ key: "recorded_at", direction: "desc" }}
          emptyText={t("noHistory")}
          locale={locale}
        />
        <p className="text-xs text-muted-foreground">{t("ledgerNote")}</p>
      </section>
    </div>
  )
}
