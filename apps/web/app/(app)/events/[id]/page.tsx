"use client"

import { useParams } from "next/navigation"
import { EventDetailView } from "@/components/events/event-detail-view"

export default function EventDetailPage() {
  const { id } = useParams<{ id: string }>()

  // key={id} forces a remount when navigating between events so form state
  // is reinitialized cleanly from the new event's data.
  return <EventDetailView key={id} eventId={id} />
}
