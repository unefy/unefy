import { redirect } from "next/navigation"
import { getSession } from "@/lib/auth"
import { AppSidebar } from "@/components/layout/app-sidebar"

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const session = await getSession()

  if (!session) {
    redirect("/login")
  }

  if (session.needs_onboarding) {
    redirect("/onboarding")
  }

  return (
    <div className="flex h-screen">
      <AppSidebar
        user={session.user}
        tenantName={session.tenant_short_name || session.tenant_name || "My Club"}
      />
      <main className="flex-1 overflow-auto">
        <div className="px-8 py-8">{children}</div>
      </main>
    </div>
  )
}
