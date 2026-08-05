"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"

import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"

export type MemberTab = {
  /** Route segment below the member id; "" is the overview. */
  segment: string
  label: string
}

/**
 * The tab bar of a member detail page — shadcn pill tabs in link mode.
 *
 * Each trigger renders as a `Link` to a sub-route rather than switching a
 * panel: every tab is addressable, survives a reload, and loads only its own
 * data. The `Tabs` value merely mirrors the current URL so the pills show the
 * right active state.
 */
export function MemberTabs({
  baseHref,
  tabs,
}: {
  baseHref: string
  tabs: MemberTab[]
}) {
  const pathname = usePathname()
  const active =
    tabs.find(
      (tab) =>
        (tab.segment ? `${baseHref}/${tab.segment}` : baseHref) === pathname
    )?.segment ?? ""

  return (
    <div className="max-w-full overflow-x-auto">
      <Tabs value={active}>
        <TabsList>
          {tabs.map((tab) => (
            <TabsTrigger
              key={tab.segment}
              value={tab.segment}
              nativeButton={false}
              render={
                <Link
                  href={tab.segment ? `${baseHref}/${tab.segment}` : baseHref}
                />
              }
            >
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
    </div>
  )
}
