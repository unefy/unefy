import { notFound } from "next/navigation"
import { getTranslations } from "next-intl/server"

import { MemberAccess } from "@/components/members/member-access"
import { DateCell } from "@/components/ui/date-cell"
import { genderLabel } from "@/lib/labels"
import { getClubAccess, getMember, listMemberFederations } from "@/lib/members"

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

/** Overview tab: master data, federations and account access. */
export default async function MemberOverviewPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const [t, tl, { id }] = await Promise.all([
    getTranslations("members"),
    getTranslations("admin"),
    params,
  ])

  // Deduped with the layout's fetch via React cache().
  const member = await getMember(id).catch(() => null)
  if (!member) notFound()

  // Access management is restricted to owner/admin, so a board member reading
  // this page gets null rather than an error — the section then stays hidden.
  const access = await getClubAccess().catch(() => null)

  const federations = await listMemberFederations(id).catch(() => [])

  const linkedAccount =
    access && member.user_id
      ? (access.members.find((m) => m.user_id === member.user_id) ?? null)
      : null
  const openInvitation =
    access?.invitations.find((i) => i.member_id === member.id) ?? null

  const address = [
    member.street,
    [member.zip_code, member.city].filter(Boolean).join(" "),
    member.country,
  ]
    .filter((part) => part?.trim())
    .join(", ")

  return (
    <>
      <section className="space-y-3">
        <h2 className="text-sm font-medium text-muted-foreground">
          {t("detail.contact")}
        </h2>
        <dl className="grid gap-4 rounded-md border p-4 sm:grid-cols-2 lg:grid-cols-4">
          <Fact label={t("detail.fields.email")} value={member.email} />
          <Fact label={t("detail.fields.phone")} value={member.phone} />
          <Fact label={t("detail.fields.mobile")} value={member.mobile} />
          <Fact label={t("detail.fields.address")} value={address || null} />
        </dl>
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-medium text-muted-foreground">
          {t("detail.membership")}
        </h2>
        <dl className="grid gap-4 rounded-md border p-4 sm:grid-cols-2 lg:grid-cols-4">
          <Fact label={t("detail.fields.category")} value={member.category} />
          <Fact label={t("detail.fields.joinedAt")}>
            <DateCell value={member.joined_at} dateOnly />
          </Fact>
          <Fact label={t("detail.fields.leftAt")}>
            <DateCell value={member.left_at} dateOnly />
          </Fact>
          <Fact label={t("detail.fields.birthday")}>
            <DateCell value={member.birthday} dateOnly />
          </Fact>
          <Fact
            label={t("detail.fields.gender")}
            value={member.gender ? genderLabel(tl, member.gender) : null}
          />
        </dl>
      </section>

      {federations.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm font-medium text-muted-foreground">
            {t("detail.federations")}
          </h2>
          <div className="space-y-3">
            {federations.map((federation) => (
              <dl
                key={federation.id}
                className="grid gap-4 rounded-md border p-4 sm:grid-cols-2 lg:grid-cols-4"
              >
                <Fact
                  label={t("detail.fields.federation")}
                  value={federation.federation}
                />
                <Fact
                  label={t("detail.fields.federationNumber")}
                  value={federation.federation_number}
                />
                <Fact label={t("detail.fields.federationJoinedAt")}>
                  <DateCell value={federation.joined_at} dateOnly />
                </Fact>
                <Fact label={t("detail.fields.federationLeftAt")}>
                  <DateCell value={federation.left_at} dateOnly />
                </Fact>
              </dl>
            ))}
          </div>
        </section>
      )}

      {access && (
        <MemberAccess
          member={member}
          access={linkedAccount}
          invitation={openInvitation}
          availableAccounts={access.members.filter((m) => m.member_id === null)}
        />
      )}
    </>
  )
}
