"use client"

import { useParams } from "next/navigation"
import { CompetitionDetailView } from "@/components/competitions/competition-detail-view"

export default function CompetitionDetailPage() {
  const { id } = useParams<{ id: string }>()

  // key={id} forces a remount when navigating between competitions so form
  // state is reinitialized cleanly from the new competition's data.
  return <CompetitionDetailView key={id} competitionId={id} />
}
