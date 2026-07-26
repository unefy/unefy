"use client"

import { useMemo, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useTranslations, useLocale } from "next-intl"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { PageHeader } from "@/components/layout/page-header"
import { SectionHeading } from "@/components/layout/section-heading"
import { ConfirmDialog } from "@/components/common/confirm-dialog"
import {
  useCompetition,
  useCompetitionSessions,
  useCreateEntry,
  useDeleteEntry,
  useSessionEntries,
  useUpdateEntry,
} from "@/hooks/use-competitions"
import { useMembers } from "@/hooks/use-members"
import { useErrorMessage } from "@/lib/errors"
import { formatDate } from "@/lib/date"
import { HugeiconsIcon } from "@hugeicons/react"
import { Delete02Icon, PencilEdit02Icon } from "@hugeicons/core-free-icons"
import type { CompetitionEntry } from "@/lib/types/competition"

interface CompetitionSessionDetailViewProps {
  competitionId: string
  sessionId: string
}

const EMPTY_ENTRY_FORM = { memberId: "", score: "", notes: "" }

export function CompetitionSessionDetailView({
  competitionId,
  sessionId,
}: CompetitionSessionDetailViewProps) {
  const t = useTranslations("competitions")
  const tc = useTranslations("common")
  const locale = useLocale()
  const router = useRouter()
  const getErrorMessage = useErrorMessage()

  const { data: competition } = useCompetition(competitionId)
  const { data: sessionsData } = useCompetitionSessions(competitionId)
  const { data: entriesData, isLoading } = useSessionEntries(
    competitionId,
    sessionId,
  )
  const { data: membersData } = useMembers({ per_page: 100 })
  const createEntry = useCreateEntry(competitionId, sessionId)
  const updateEntry = useUpdateEntry(competitionId, sessionId)
  const deleteEntry = useDeleteEntry(competitionId, sessionId)

  const [dialogOpen, setDialogOpen] = useState(false)
  const [editEntry, setEditEntry] = useState<CompetitionEntry | null>(null)
  const [form, setForm] = useState({ ...EMPTY_ENTRY_FORM })
  const [deleteId, setDeleteId] = useState<string | null>(null)

  const session = sessionsData?.data.find((s) => s.id === sessionId)

  const memberNames = useMemo(() => {
    const map = new Map<string, string>()
    for (const m of membersData?.data ?? []) {
      map.set(m.id, `${m.first_name} ${m.last_name}`)
    }
    return map
  }, [membersData])

  const entries = useMemo(() => {
    const list = [...(entriesData?.data ?? [])]
    const reverse = competition?.scoring_mode !== "lowest_wins"
    list.sort((a, b) =>
      reverse ? b.score_value - a.score_value : a.score_value - b.score_value,
    )
    return list
  }, [entriesData, competition])

  const memberItems = (membersData?.data ?? []).map((m) => ({
    value: m.id,
    label: `${m.first_name} ${m.last_name}`,
  }))

  function openCreate() {
    setEditEntry(null)
    setForm({ ...EMPTY_ENTRY_FORM })
    setDialogOpen(true)
  }

  function openEdit(entry: CompetitionEntry) {
    setEditEntry(entry)
    setForm({
      memberId: entry.member_id,
      score: String(entry.score_value),
      notes: entry.notes ?? "",
    })
    setDialogOpen(true)
  }

  function handleClose() {
    setDialogOpen(false)
    setEditEntry(null)
    setForm({ ...EMPTY_ENTRY_FORM })
  }

  const scoreValue = Number.parseFloat(form.score.replace(",", "."))
  const scoreValid = Number.isFinite(scoreValue) && scoreValue >= 0

  function handleSave() {
    if (!scoreValid) return
    const options = {
      onSuccess: () => {
        toast.success(tc("saved"))
        handleClose()
      },
      onError: (err: unknown) => toast.error(getErrorMessage(err)),
    }
    if (editEntry) {
      updateEntry.mutate(
        {
          entryId: editEntry.id,
          data: { score_value: scoreValue, notes: form.notes.trim() || null },
        },
        options,
      )
    } else {
      createEntry.mutate(
        {
          member_id: form.memberId,
          score_value: scoreValue,
          score_unit: competition?.scoring_unit,
          discipline: session?.discipline ?? null,
          recorded_at: new Date().toISOString(),
          notes: form.notes.trim() || null,
        },
        options,
      )
    }
  }

  function handleDelete() {
    if (!deleteId) return
    deleteEntry.mutate(deleteId, {
      onSuccess: () => {
        toast.success(tc("saved"))
        setDeleteId(null)
      },
      onError: (err) => toast.error(getErrorMessage(err)),
    })
  }

  if (!session || !competition) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 animate-pulse rounded bg-muted" />
        <div className="h-64 animate-pulse rounded-2xl bg-muted" />
      </div>
    )
  }

  const pending = createEntry.isPending || updateEntry.isPending

  return (
    <div className="space-y-6">
      <PageHeader
        title={session.name || formatDate(session.date, locale)}
        description={
          <span className="flex items-center gap-2">
            <Badge variant="secondary">{competition.name}</Badge>
            <span className="text-muted-foreground text-sm">
              {formatDate(session.date, locale)}
              {session.discipline ? ` · ${session.discipline}` : ""}
              {session.location ? ` · ${session.location}` : ""}
            </span>
          </span>
        }
      >
        <Button
          variant="outline"
          onClick={() => router.push(`/competitions/${competitionId}`)}
        >
          ← {competition.name}
        </Button>
      </PageHeader>

      <div className="flex items-start justify-between">
        <SectionHeading
          title={t("results")}
          description={t("resultsDescription")}
        />
        <Button variant="outline" size="sm" onClick={openCreate}>
          {t("addResult")}
        </Button>
      </div>

      {isLoading ? (
        <div className="h-32 animate-pulse rounded-xl bg-muted" />
      ) : entries.length === 0 ? (
        <p className="text-muted-foreground py-6 text-center text-sm">
          {t("noResults")}
        </p>
      ) : (
        <div className="rounded-xl border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-12">#</TableHead>
                <TableHead>{t("member")}</TableHead>
                <TableHead className="text-right">{t("score")}</TableHead>
                <TableHead>{t("notes")}</TableHead>
                <TableHead className="w-20" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {entries.map((entry, index) => (
                <TableRow key={entry.id}>
                  <TableCell className="text-muted-foreground">
                    {index + 1}
                  </TableCell>
                  <TableCell>
                    <Link
                      href={`/members/${entry.member_id}`}
                      className="font-medium hover:underline"
                    >
                      {memberNames.get(entry.member_id) ?? t("unknownMember")}
                    </Link>
                  </TableCell>
                  <TableCell className="text-right font-medium tabular-nums">
                    {entry.score_value.toLocaleString(locale)}{" "}
                    <span className="text-muted-foreground font-normal">
                      {entry.score_unit}
                    </span>
                  </TableCell>
                  <TableCell className="text-muted-foreground max-w-64 truncate text-sm">
                    {entry.notes}
                  </TableCell>
                  <TableCell>
                    <div className="flex justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => openEdit(entry)}
                        aria-label={tc("edit")}
                      >
                        <HugeiconsIcon icon={PencilEdit02Icon} size={14} />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => setDeleteId(entry.id)}
                        aria-label={tc("delete")}
                      >
                        <HugeiconsIcon icon={Delete02Icon} size={14} />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <Dialog open={dialogOpen} onOpenChange={(v) => !v && handleClose()}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>
              {editEntry ? t("editResult") : t("addResult")}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            {!editEntry && (
              <div className="space-y-2">
                <Label>{t("member")} *</Label>
                <Select
                  items={memberItems}
                  value={form.memberId || null}
                  onValueChange={(v) =>
                    setForm((p) => ({ ...p, memberId: v ?? "" }))
                  }
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder={t("selectMember")} />
                  </SelectTrigger>
                  <SelectContent>
                    {memberItems.map((item) => (
                      <SelectItem key={item.value} value={item.value}>
                        {item.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            <div className="space-y-2">
              <Label>
                {t("score")} ({competition.scoring_unit}) *
              </Label>
              <Input
                inputMode="decimal"
                value={form.score}
                onChange={(e) =>
                  setForm((p) => ({ ...p, score: e.target.value }))
                }
              />
            </div>
            <div className="space-y-2">
              <Label>{t("notes")}</Label>
              <Textarea
                rows={2}
                value={form.notes}
                onChange={(e) =>
                  setForm((p) => ({ ...p, notes: e.target.value }))
                }
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={handleClose}>
              {tc("cancel")}
            </Button>
            <Button
              onClick={handleSave}
              disabled={
                pending || !scoreValid || (!editEntry && !form.memberId)
              }
            >
              {pending ? tc("saving") : tc("save")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={deleteId !== null}
        onOpenChange={(v) => !v && setDeleteId(null)}
        title={t("deleteResult")}
        description={t("deleteResultConfirm")}
        destructive
        pending={deleteEntry.isPending}
        onConfirm={handleDelete}
      />
    </div>
  )
}
