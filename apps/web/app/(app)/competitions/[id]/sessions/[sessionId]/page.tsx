"use client"

import { useParams } from "next/navigation"
import { CompetitionSessionDetailView } from "@/components/competitions/competition-session-detail-view"

export default function CompetitionSessionDetailPage() {
  const { id, sessionId } = useParams<{ id: string; sessionId: string }>()

  return (
    <CompetitionSessionDetailView
      key={sessionId}
      competitionId={id}
      sessionId={sessionId}
    />
  )
}
