"use client"

import Link from "next/link"

import { NavMain } from "@/components/layout/nav-main"
import { NavUser } from "@/components/layout/nav-user"
import { sidebarData } from "@/components/layout/sidebar-data"
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
import { ShieldIcon } from "lucide-react"

type AppSidebarProps = React.ComponentProps<typeof Sidebar> & {
  session: Session
  tenants: TenantMembership[]
}

export function AppSidebar({ session, tenants, ...props }: AppSidebarProps) {
  const clubName = session.tenant_short_name || session.tenant_name || "unefy"

  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" render={<Link href="/" />}>
              <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
                <ShieldIcon className="size-4" />
              </div>
              <div className="grid flex-1 text-start text-sm leading-tight">
                <span className="truncate font-semibold">{clubName}</span>
                <span className="truncate text-xs">unefy</span>
              </div>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <NavMain navGroups={sidebarData.navGroups} />
      </SidebarContent>
      <SidebarFooter>
        <NavUser session={session} tenants={tenants} />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
