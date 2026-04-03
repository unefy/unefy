import { Suspense } from "react"
import { apiCall } from "@/lib/api"
import { SettingsShell } from "@/components/settings/settings-shell"
import { SettingsSkeleton } from "@/components/skeletons/settings-skeleton"
import type { Club } from "@/lib/types/club"

async function SettingsData({ children }: { children: React.ReactNode }) {
  const res = await apiCall<{ data: Club }>("/api/v1/club")
  return <SettingsShell club={res.data}>{children}</SettingsShell>
}

export default function SettingsLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <Suspense fallback={<SettingsSkeleton />}>
      <SettingsData>{children}</SettingsData>
    </Suspense>
  )
}
