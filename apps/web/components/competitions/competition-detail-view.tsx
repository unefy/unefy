"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { PageHeader } from "@/components/layout/page-header"
import { SectionHeading } from "@/components/layout/section-heading"
import { ConfirmDialog } from "@/components/common/confirm-dialog"
import {
  CompetitionFormFields,
  competitionFormToPayload,
  competitionToFormState,
  EMPTY_COMPETITION_FORM,
  type CompetitionFormState,
} from "@/components/competitions/competition-form-fields"
import { CompetitionEventsSection } from "@/components/competitions/competition-events-section"
import { CompetitionScoreboardSection } from "@/components/competitions/competition-scoreboard-section"
import { CompetitionSessionsSection } from "@/components/competitions/competition-sessions-section"
import {
  useCompetition,
  useDeleteCompetition,
  useUpdateCompetition,
} from "@/hooks/use-competitions"
import { useErrorMessage } from "@/lib/errors"

interface CompetitionDetailViewProps {
  competitionId: string
}

export function CompetitionDetailView({
  competitionId,
}: CompetitionDetailViewProps) {
  const t = useTranslations("competitions")
  const tc = useTranslations("common")
  const router = useRouter()
  const getErrorMessage = useErrorMessage()

  const { data: competition, isLoading } = useCompetition(competitionId)
  const updateCompetition = useUpdateCompetition()
  const deleteCompetition = useDeleteCompetition()

  const [form, setForm] = useState<CompetitionFormState>({
    ...EMPTY_COMPETITION_FORM,
  })
  const [dirty, setDirty] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)

  useEffect(() => {
    if (competition) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setForm(competitionToFormState(competition))
      setDirty(false)
    }
  }, [competition])

  function handleChange<K extends keyof CompetitionFormState>(
    name: K,
    value: CompetitionFormState[K]
  ) {
    setForm((prev) => ({ ...prev, [name]: value }))
    setDirty(true)
  }

  function handleSave() {
    updateCompetition.mutate(
      { id: competitionId, data: competitionFormToPayload(form) },
      {
        onSuccess: () => {
          toast.success(tc("saved"))
          setDirty(false)
        },
        onError: (err) => toast.error(getErrorMessage(err)),
      }
    )
  }

  function handleDelete() {
    deleteCompetition.mutate(competitionId, {
      onSuccess: () => {
        toast.success(tc("saved"))
        setConfirmDelete(false)
        router.push("/competitions")
      },
      onError: (err) => toast.error(getErrorMessage(err)),
    })
  }

  if (isLoading || !competition) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 animate-pulse rounded bg-muted" />
        <div className="h-64 animate-pulse rounded-2xl bg-muted" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={competition.name}
        description={
          <span className="flex items-center gap-2">
            <Badge variant="secondary">
              {t(`type_${competition.competition_type}`)}
            </Badge>
            <Badge variant="outline">
              {t(`scoring_${competition.scoring_mode}`)} ·{" "}
              {competition.scoring_unit}
            </Badge>
          </span>
        }
      >
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => router.push("/competitions")}
          >
            ← {t("title")}
          </Button>
          {dirty && (
            <Button onClick={handleSave} disabled={updateCompetition.isPending}>
              {updateCompetition.isPending ? tc("saving") : tc("save")}
            </Button>
          )}
          <Button variant="destructive" onClick={() => setConfirmDelete(true)}>
            {t("deleteCompetition")}
          </Button>
        </div>
      </PageHeader>

      <div className="grid gap-10 lg:grid-cols-2">
        <div>
          <SectionHeading title={t("details")} description="" />
          <CompetitionFormFields form={form} onChange={handleChange} />
        </div>
        <div className="space-y-10">
          <CompetitionSessionsSection competitionId={competitionId} />
          <CompetitionEventsSection competitionId={competitionId} />
        </div>
      </div>

      <CompetitionScoreboardSection competitionId={competitionId} />

      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title={t("deleteCompetition")}
        description={t("deleteCompetitionConfirm", { name: competition.name })}
        destructive
        pending={deleteCompetition.isPending}
        onConfirm={handleDelete}
      />
    </div>
  )
}
