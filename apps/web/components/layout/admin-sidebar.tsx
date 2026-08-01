"use client"

import Link from "next/link"
import { useTranslations } from "next-intl"

import { adminSidebarData } from "@/components/layout/admin-sidebar-data"
import { NavMain } from "@/components/layout/nav-main"
import { NavUser } from "@/components/layout/nav-user"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "@/components/ui/sidebar"
import type { Session, TenantMembership } from "@/lib/auth"
import { ArrowLeftIcon, ShieldCheckIcon } from "lucide-react"

type AdminSidebarProps = React.ComponentProps<typeof Sidebar> & {
  session: Session
  tenants: TenantMembership[]
}

export function AdminSidebar({
  session,
  tenants,
  ...props
}: AdminSidebarProps) {
  const t = useTranslations("adminNav")

  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" render={<Link href="/admin" />}>
              {/* Visually distinct from the club shell on purpose — an admin
                  must never be unsure which of the two apps they are in. */}
              <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-destructive text-white">
                <ShieldCheckIcon className="size-4" />
              </div>
              <div className="grid flex-1 text-start text-sm leading-tight">
                <span className="truncate font-semibold">{t("title")}</span>
                <span className="truncate text-xs">unefy</span>
              </div>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        <NavMain navGroups={adminSidebarData.navGroups} namespace="adminNav" />
      </SidebarContent>

      <SidebarFooter>
        {session.tenant_id && (
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton
                tooltip={t("backToClub")}
                render={<Link href="/" />}
              >
                <ArrowLeftIcon />
                <span>{t("backToClub")}</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        )}
        <NavUser session={session} tenants={tenants} />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
