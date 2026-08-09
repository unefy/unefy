import { getTranslations } from "next-intl/server"

import { AssignmentsPanel } from "@/components/dues/assignments-panel"
import { DuesTable } from "@/components/dues/dues-table"
import { getClubTimeZone } from "@/lib/attendance"
import { getSession } from "@/lib/auth"
import {
  listFeeTypes,
  listMemberDues,
  listMemberFeeAssignments,
} from "@/lib/dues"

const BOARD_ROLES = ["owner", "admin", "board"]

/** The club's own today, not the browser's — see `lib/time`. */
function clubToday(timeZone: string): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone }).format(new Date())
}

/** Dues tab: the member's fee assignments and their billing history. */
export default async function MemberDuesPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const [t, timeZone, session, { id }] = await Promise.all([
    getTranslations("members.detail.duesTab"),
    getClubTimeZone(),
    getSession(),
    params,
  ])

  const [assignments, dues, feeTypes] = await Promise.all([
    listMemberFeeAssignments(id).catch(() => []),
    listMemberDues(id).catch(() => []),
    // Only active types can be assigned; retired ones stay resolvable by id
    // because the assignment rows still name them.
    listFeeTypes(true).catch(() => []),
  ])

  const canManage = BOARD_ROLES.includes(session?.role ?? "")

  return (
    <>
      <section className="space-y-3">
        <h2 className="text-sm font-medium text-muted-foreground">
          {t("assignments")}
        </h2>
        <AssignmentsPanel
          memberId={id}
          assignments={assignments}
          feeTypes={feeTypes.filter((fee) => fee.is_active)}
          canManage={canManage}
        />
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-medium text-muted-foreground">
          {t("history")}
        </h2>
        <DuesTable
          dues={dues}
          timeZone={timeZone}
          today={clubToday(timeZone)}
          canManage={canManage}
        />
      </section>
    </>
  )
}
