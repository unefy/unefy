import { getTranslations } from "next-intl/server"

import { MemberFunctions } from "@/components/members/member-functions"
import { getClub } from "@/lib/club"
import {
  listActiveFunctions,
  listClubDivisions,
  listMemberFunctions,
} from "@/lib/functions"
import { getClubAccess, getMember } from "@/lib/members"

/** Functions tab: the member's offices — current terms first, history below. */
export default async function MemberFunctionsPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const [{ id }] = await Promise.all([params, getTranslations("members")])

  const [assignments, functions, club, member, access] = await Promise.all([
    listMemberFunctions(id).catch(() => []),
    listActiveFunctions().catch(() => []),
    getClub().catch(() => null),
    getMember(id).catch(() => null),
    // Only for the suggested-role hint in the assign dialog.
    getClubAccess().catch(() => null),
  ])

  const hasDivisions = club?.has_divisions ?? false
  const divisions = hasDivisions
    ? await listClubDivisions().catch(() => [])
    : []

  const linkedRole =
    access && member?.user_id
      ? (access.members.find((m) => m.user_id === member.user_id)?.role ?? null)
      : null

  return (
    <MemberFunctions
      memberId={id}
      assignments={assignments}
      functions={functions}
      divisions={divisions}
      hasDivisions={hasDivisions}
      linkedRole={linkedRole}
    />
  )
}
