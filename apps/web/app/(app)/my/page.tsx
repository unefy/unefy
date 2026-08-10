import { getTranslations } from "next-intl/server"

import { DateCell } from "@/components/ui/date-cell"
import { genderLabel } from "@/lib/labels"
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
 * The signed-in person's own register entry.
 *
 * Reads exclusively through `/members/me`, which resolves via the
 * account↔member link and can never show anyone else's record.
 */
export default async function MyProfilePage() {
  const [t, tl] = await Promise.all([
    getTranslations("my"),
    getTranslations("admin"),
  ])

  // 404 here is a state, not an error: the account exists without a register
  // entry (treasurer, external trainer, or simply not linked yet).
  const member = await getMyMember().catch(() => null)

  if (!member) {
    return (
      <div className="rounded-md border p-6 text-sm text-muted-foreground">
        {t("notLinked")}
      </div>
    )
  }

  return (
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
  )
}
