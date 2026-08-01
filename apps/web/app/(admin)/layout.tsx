import { cookies } from "next/headers"
import { redirect } from "next/navigation"

import { AdminSidebar } from "@/components/layout/admin-sidebar"
import { Header } from "@/components/layout/header"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import { TooltipProvider } from "@/components/ui/tooltip"
import { getSession, getTenants } from "@/lib/auth"
import { cn } from "@/lib/utils"

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const session = await getSession()
  if (!session) {
    redirect("/login")
  }

  // A UX guard, not the security boundary: every `/api/v1/admin/…` call is
  // independently gated by `require_platform_admin` on the backend. Sending a
  // non-admin to the club app rather than showing a 403 avoids advertising
  // that the area exists at all.
  if (!session.is_superuser || session.impersonator) {
    redirect("/")
  }

  const [tenants, cookieStore] = await Promise.all([getTenants(), cookies()])
  const defaultOpen = cookieStore.get("sidebar_state")?.value !== "false"

  return (
    <TooltipProvider>
      <SidebarProvider defaultOpen={defaultOpen}>
        <AdminSidebar session={session} tenants={tenants} />
        <SidebarInset
          className={cn(
            "@container/content",
            "has-data-[layout=fixed]:h-svh",
            "peer-data-[variant=inset]:has-data-[layout=fixed]:h-[calc(100svh-(var(--spacing)*4))]"
          )}
        >
          <Header fixed />
          <div className="flex flex-1 flex-col gap-4 p-4 md:gap-6 md:p-6">
            {children}
          </div>
        </SidebarInset>
      </SidebarProvider>
    </TooltipProvider>
  )
}
