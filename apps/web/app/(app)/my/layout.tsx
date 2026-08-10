import { getTranslations } from "next-intl/server"

import { HeaderScrollTitle } from "@/components/layout/header-scroll-title"
import { MemberTabs, type MemberTab } from "@/components/members/member-tabs"
import { Badge } from "@/components/ui/badge"
import { getClub } from "@/lib/club"
import { memberStatusLabel } from "@/lib/labels"
import { getMyMember } from "@/lib/members"

/**
 * The frame the member's own area shares: who they are, and the tabs.
 *
 * Sub-routes rather than one long page, like the member detail: each tab
 * loads only its own data, and a member can link somebody to their own range
 * days without sending them through everything else.
 *
 * A 404 from `/members/me` is a state, not an error — an account can exist
 * without a register entry (treasurer, external trainer). The tabs still work;
 * they simply have nothing to show.
 */
export default async function MyLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const [t, tl] = await Promise.all([
    getTranslations("my"),
    getTranslations("admin"),
  ])

  const member = await getMyMember().catch(() => null)
  const club = await getClub().catch(() => null)

  const tabs: MemberTab[] = [
    { segment: "", label: t("tabs.profile") },
    { segment: "dues", label: t("tabs.dues") },
    { segment: "attendance", label: t("tabs.attendance") },
    { segment: "functions", label: t("tabs.functions") },
    { segment: "events", label: t("tabs.events") },
  ]

  return (
    <>
      <div className="-mt-2 space-y-2 md:-mt-3">
        <div className="flex flex-wrap items-center gap-3">
          <HeaderScrollTitle title={t("title")} />
          <h1 className="text-2xl font-semibold tracking-tight">
            {t("title")}
          </h1>
          {member && (
            <>
              <Badge variant="secondary">
                {memberStatusLabel(tl, member.status)}
              </Badge>
              <span className="font-mono text-sm text-muted-foreground">
                {member.member_number}
              </span>
            </>
          )}
        </div>
        <p className="text-sm text-muted-foreground">
          {member
            ? t("subtitleFor", {
                name: `${member.first_name} ${member.last_name}`,
                club: club?.name ?? "",
              })
            : t("subtitle")}
        </p>
        <MemberTabs baseHref="/my" tabs={tabs} />
      </div>

      {children}
    </>
  )
}
