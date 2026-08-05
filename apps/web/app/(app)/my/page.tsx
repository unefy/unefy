import { getTranslations } from "next-intl/server"

import { Badge } from "@/components/ui/badge"
import { DateCell } from "@/components/ui/date-cell"
import { genderLabel, memberStatusLabel } from "@/lib/labels"
import { listMyDues } from "@/lib/dues"
import { getMyMember } from "@/lib/members"

function Fact({
  label,
  value,
  children,
}: {
  label: string
  value?: string | null
  children?: React.ReactNode
}) {
  return (
    <div className="space-y-1">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-sm">{children ?? (value?.trim() ? value : "—")}</dd>
    </div>
  )
}

/**
 * The signed-in person's own view: their register entry and their dues.
 *
 * Every role gets this page — it reads exclusively through the `/me`
 * endpoints, which resolve via the account↔member link and can never show
 * anyone else's data.
 */
export default async function MyPage() {
  const [t, tl] = await Promise.all([
    getTranslations("my"),
    getTranslations("admin"),
  ])

  // 404 here is a state, not an error: the account exists without a register
  // entry (treasurer, external trainer, or simply not linked yet).
  const member = await getMyMember().catch(() => null)
  const dues = member ? await listMyDues().catch(() => []) : []

  return (
    <>
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
        <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
      </div>

      {!member ? (
        <div className="rounded-md border p-6 text-sm text-muted-foreground">
          {t("notLinked")}
        </div>
      ) : (
        <>
          <section className="space-y-3">
            <div className="flex flex-wrap items-center gap-3">
              <h2 className="text-sm font-medium text-muted-foreground">
                {t("profile")}
              </h2>
              <Badge variant="secondary">
                {memberStatusLabel(tl, member.status)}
              </Badge>
            </div>
            <dl className="grid gap-4 rounded-md border p-4 sm:grid-cols-2 lg:grid-cols-4">
              <Fact label={t("fields.memberNumber")}>
                <span className="font-mono">{member.member_number}</span>
              </Fact>
              <Fact
                label={t("fields.name")}
                value={`${member.first_name} ${member.last_name}`}
              />
              <Fact label={t("fields.joinedAt")}>
                <DateCell value={member.joined_at} dateOnly />
              </Fact>
              <Fact label={t("fields.birthday")}>
                <DateCell value={member.birthday} dateOnly />
              </Fact>
              <Fact
                label={t("fields.gender")}
                value={member.gender ? genderLabel(tl, member.gender) : null}
              />
              <Fact label={t("fields.email")} value={member.email} />
              <Fact
                label={t("fields.address")}
                value={
                  [
                    member.street,
                    [member.zip_code, member.city].filter(Boolean).join(" "),
                  ]
                    .filter((part) => part?.trim())
                    .join(", ") || null
                }
              />
              <Fact label={t("fields.category")} value={member.category} />
            </dl>
          </section>

          <section className="space-y-3">
            <h2 className="text-sm font-medium text-muted-foreground">
              {t("dues")}
            </h2>
            {dues.length === 0 ? (
              <div className="rounded-md border p-4 text-sm text-muted-foreground">
                {t("noDues")}
              </div>
            ) : (
              <div className="overflow-x-auto rounded-md border">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-start text-xs text-muted-foreground">
                      <th className="p-3 text-start font-medium">
                        {t("dueFields.fee")}
                      </th>
                      <th className="p-3 text-start font-medium">
                        {t("dueFields.period")}
                      </th>
                      <th className="p-3 text-start font-medium">
                        {t("dueFields.amount")}
                      </th>
                      <th className="p-3 text-start font-medium">
                        {t("dueFields.status")}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {dues.map((due) => (
                      <tr key={due.id} className="border-b last:border-b-0">
                        <td className="p-3">{due.fee_name}</td>
                        <td className="p-3">
                          {due.period_start.slice(0, 4)}
                        </td>
                        <td className="p-3 font-mono">
                          {Number(due.amount).toLocaleString("de-DE", {
                            style: "currency",
                            currency: "EUR",
                          })}
                        </td>
                        <td className="p-3">
                          <Badge
                            variant={
                              due.status === "open" ? "destructive" : "secondary"
                            }
                          >
                            {t(`dueStatus.${due.status}`)}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </>
  )
}
