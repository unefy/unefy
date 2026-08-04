import { cookies } from "next/headers"
import { redirect } from "next/navigation"

import { ImpersonationBanner } from "@/components/admin/impersonation-banner"
import { AppSidebar } from "@/components/layout/app-sidebar"
import { LiveUpdates } from "@/components/live-updates"
import { Header } from "@/components/layout/header"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import { TooltipProvider } from "@/components/ui/tooltip"
import { getSession, getTenants } from "@/lib/auth"
import { getClub } from "@/lib/club"
import { cn } from "@/lib/utils"

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode
}) {
  // This is the real gate: proxy.ts only checks that a cookie is present,
  // here the session is verified against the backend.
  const session = await getSession()
  if (!session) {
    redirect("/login")
  }

  // Signed in but not attached to a club yet — onboarding first.
  if (session.needs_onboarding) {
    redirect("/onboarding")
  }

  // Modules gate nav sections (e.g. Schießsport). Failing open with none:
  // a club read hiccup must not blank the whole shell, only module entries.
  const [tenants, cookieStore, club] = await Promise.all([
    getTenants(),
    cookies(),
    getClub().catch(() => null),
  ])

  // The sidebar writes its collapsed state to this cookie, so the server can
  // render the correct width immediately and avoid a layout shift.
  const defaultOpen = cookieStore.get("sidebar_state")?.value !== "false"

  return (
    <TooltipProvider>
      {/* One change stream for the whole shell — see the component for why here. */}
      <LiveUpdates />
      <SidebarProvider defaultOpen={defaultOpen}>
        <AppSidebar
          session={session}
          tenants={tenants}
          modules={club?.modules ?? []}
        />
        <SidebarInset
          className={cn(
            "@container/content",
            "has-data-[layout=fixed]:h-svh",
            "peer-data-[variant=inset]:has-data-[layout=fixed]:h-[calc(100svh-(var(--spacing)*4))]"
          )}
        >
          {session.impersonator && (
            <ImpersonationBanner
              impersonator={session.impersonator}
              userName={session.user.name ?? session.user.email}
            />
          )}
          <Header fixed />
          <div className="flex flex-1 flex-col gap-4 p-4 md:gap-6 md:p-6">
            {children}
          </div>
        </SidebarInset>
      </SidebarProvider>
    </TooltipProvider>
  )
}
