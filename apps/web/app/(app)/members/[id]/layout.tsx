"use client"

import { useParams } from "next/navigation"
import { MemberDetailShell } from "@/components/members/member-detail-shell"

export default function MemberDetailLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const { id } = useParams<{ id: string }>()

  return <MemberDetailShell memberId={id}>{children}</MemberDetailShell>
}
