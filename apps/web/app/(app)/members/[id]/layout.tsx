import Link from "next/link"
import { notFound, redirect } from "next/navigation"
import { getTranslations } from "next-intl/server"

import { deleteMemberAction } from "@/actions/members"
import { ConfirmDelete } from "@/components/admin/confirm-delete"
import { MemberDialog } from "@/components/members/member-dialog"
import { MemberTabs, type MemberTab } from "@/components/members/member-tabs"
import { Badge } from "@/components/ui/badge"
import { getClub } from "@/lib/club"
import { memberStatusLabel } from "@/lib/labels"
import { getClubAccess, getMember } from "@/lib/members"
import { ArrowLeftIcon } from "lucide-react"

/**
 * The frame every member tab shares: back link, record header with actions,
 * and the tab bar. The tabs are sub-routes, so each one loads only its own
 * data — the overview does not pay for the attendance history.
 */
export default async function MemberDetailLayout({
  params,
  children,
}: {
  params: Promise<{ id: string }>
  children: React.ReactNode
}) {
  const [t, tl, tf, { id }] = await Promise.all([
    getTranslations("members"),
    getTranslations("admin"),
    getTranslations("members.form"),
    params,
  ])

  const member = await getMember(id).catch(() => null)
  if (!member) notFound()

  // Only for the edit dialog's block-access offer; the section itself lives
  // on the overview tab.
  const access = await getClubAccess().catch(() => null)
  const linkedAccount =
    access && member.user_id
      ? (access.members.find((m) => m.user_id === member.user_id) ?? null)
      : null

  const club = await getClub().catch(() => null)

  const tabs: MemberTab[] = [
    { segment: "", label: t("detail.tabs.overview") },
    { segment: "dues", label: t("detail.tabs.dues") },
    { segment: "attendance", label: t("detail.tabs.attendance") },
    ...(club?.modules.includes("shooting")
      ? [{ segment: "shooting", label: t("detail.tabs.shooting") }]
      : []),
  ]

  return (
    <>
      {/* Sticky below the app topbar (h-16): name and tabs stay in view while
          a long tab body scrolls. The negative margins undo the content
          padding so the bar spans the full width and sits close under the
          topbar instead of floating in it. */}
      <div className="sticky top-16 z-40 -mx-4 -mt-4 space-y-2 border-b bg-background/95 px-4 pt-1 pb-3 backdrop-blur md:-mx-6 md:-mt-6 md:px-6">
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
          <span className="font-mono text-sm text-muted-foreground">
            {member.member_number}
          </span>
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
        <MemberTabs baseHref={`/members/${member.id}`} tabs={tabs} />
      </div>

      {children}
    </>
  )
}
