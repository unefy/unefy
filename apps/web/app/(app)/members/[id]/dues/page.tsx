import { getTranslations } from "next-intl/server"

import { Badge } from "@/components/ui/badge"
import { DateCell } from "@/components/ui/date-cell"
import {
  listFeeTypes,
  listMemberDues,
  listMemberFeeAssignments,
} from "@/lib/dues"

function euro(amount: string) {
  return Number(amount).toLocaleString("de-DE", {
    style: "currency",
    currency: "EUR",
  })
}

/** Dues tab: the member's fee assignments and their billing history. */
export default async function MemberDuesPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const [t, { id }] = await Promise.all([
    getTranslations("members.detail.duesTab"),
    params,
  ])

  const [assignments, dues, feeTypes] = await Promise.all([
    listMemberFeeAssignments(id).catch(() => []),
    listMemberDues(id).catch(() => []),
    listFeeTypes().catch(() => []),
  ])
  const feeNameById = new Map(feeTypes.map((fee) => [fee.id, fee.name]))

  return (
    <>
      <section className="space-y-3">
        <h2 className="text-sm font-medium text-muted-foreground">
          {t("assignments")}
        </h2>
        {assignments.length === 0 ? (
          <div className="rounded-md border p-4 text-sm text-muted-foreground">
            {t("noAssignments")}
          </div>
        ) : (
          <div className="space-y-3">
            {assignments.map((assignment) => (
              <div
                key={assignment.id}
                className="flex flex-wrap items-center gap-3 rounded-md border p-4 text-sm"
              >
                <span className="font-medium">
                  {feeNameById.get(assignment.fee_type_id) ?? "—"}
                </span>
                <span className="text-muted-foreground">
                  {t("validFrom")} <DateCell value={assignment.valid_from} dateOnly />
                </span>
                {assignment.valid_to && (
                  <span className="text-muted-foreground">
                    {t("validTo")} <DateCell value={assignment.valid_to} dateOnly />
                  </span>
                )}
                {assignment.note && (
                  <span className="text-muted-foreground">{assignment.note}</span>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-medium text-muted-foreground">
          {t("history")}
        </h2>
        {dues.length === 0 ? (
          <div className="rounded-md border p-4 text-sm text-muted-foreground">
            {t("noDues")}
          </div>
        ) : (
          <div className="overflow-x-auto rounded-md border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-xs text-muted-foreground">
                  <th className="p-3 text-start font-medium">{t("fee")}</th>
                  <th className="p-3 text-start font-medium">{t("year")}</th>
                  <th className="p-3 text-start font-medium">{t("amount")}</th>
                  <th className="p-3 text-start font-medium">{t("status")}</th>
                  <th className="p-3 text-start font-medium">{t("paidAt")}</th>
                </tr>
              </thead>
              <tbody>
                {dues.map((due) => (
                  <tr key={due.id} className="border-b last:border-b-0">
                    <td className="p-3">{due.fee_name}</td>
                    <td className="p-3">{due.period_start.slice(0, 4)}</td>
                    <td className="p-3 font-mono">{euro(due.amount)}</td>
                    <td className="p-3">
                      <Badge
                        variant={
                          due.status === "open" ? "destructive" : "secondary"
                        }
                      >
                        {t(`statusValues.${due.status}`)}
                      </Badge>
                    </td>
                    <td className="p-3">
                      <DateCell value={due.paid_at} dateOnly />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  )
}
