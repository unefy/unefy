import Link from "next/link"
import { notFound, redirect } from "next/navigation"
import { getTranslations } from "next-intl/server"

import { deleteMemberAction } from "@/actions/members"
import { ConfirmDelete } from "@/components/admin/confirm-delete"
import { MemberAccess } from "@/components/members/member-access"
import { MemberDialog } from "@/components/members/member-dialog"
import { Badge } from "@/components/ui/badge"
import { DateCell } from "@/components/ui/date-cell"
import { memberStatusLabel } from "@/lib/labels"
import { getClubAccess, getMember } from "@/lib/members"
import { ArrowLeftIcon } from "lucide-react"

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

export default async function MemberDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const [t, tl, tf, { id }] = await Promise.all([
    getTranslations("members"),
    getTranslations("admin"),
    getTranslations("members.form"),
    params,
  ])

  const member = await getMember(id).catch(() => null)
  if (!member) notFound()

  // Access management is restricted to owner/admin, so a board member reading
  // this page gets null rather than an error — the section then stays hidden.
  const access = await getClubAccess().catch(() => null)

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
      <div className="space-y-3">
        <Link
          href="/members"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeftIcon className="size-4" />
          {t("detail.back")}
        </Link>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">
            {member.first_name} {member.last_name}
          </h1>
          <Badge variant="secondary">
            {memberStatusLabel(tl, member.status)}
          </Badge>
          <div className="ms-auto flex items-center gap-2">
            <MemberDialog
              member={member}
              hasActiveAccount={linkedAccount?.is_active ?? false}
              accountUserId={linkedAccount?.user_id}
            />
            <ConfirmDelete
              title={tf("deleteTitle", {
                name: `${member.first_name} ${member.last_name}`,
              })}
              description={tf("deleteDescription")}
              action={async () => {
                "use server"
                const result = await deleteMemberAction(member.id)
                // The record this page shows is gone, so staying here would
                // land on a 404 — leave for the list instead.
                if (result.success) redirect("/members")
                return result
              }}
            />
          </div>
        </div>
        <p className="font-mono text-sm text-muted-foreground">
          {member.member_number}
        </p>
      </div>

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
        </dl>
      </section>

      {access && (
        <MemberAccess
          member={member}
          access={linkedAccount}
          invitation={openInvitation}
        />
      )}
    </>
  )
}
