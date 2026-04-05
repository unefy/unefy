"use client"

import { useParams } from "next/navigation"
import { MemberDetailShell } from "@/components/members/member-detail-shell"

export default function MemberDetailLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const { id } = useParams<{ id: string }>()

  // key={id} forces a remount when navigating between members so form state
  // is reinitialized cleanly from the new member's data.
  return (
    <MemberDetailShell key={id} memberId={id}>
      {children}
    </MemberDetailShell>
  )
}
