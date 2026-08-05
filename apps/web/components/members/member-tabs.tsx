"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"

import { cn } from "@/lib/utils"

export type MemberTab = {
  /** Route segment below the member id; "" is the overview. */
  segment: string
  label: string
}

/**
 * The tab bar of a member detail page. Tabs are links to sub-routes, not
 * client state — every tab is addressable and survives a reload.
 */
export function MemberTabs({
  baseHref,
  tabs,
}: {
  baseHref: string
  tabs: MemberTab[]
}) {
  const pathname = usePathname()

  return (
    <nav className="flex gap-1 overflow-x-auto border-b">
      {tabs.map((tab) => {
        const href = tab.segment ? `${baseHref}/${tab.segment}` : baseHref
        const active = pathname === href
        return (
          <Link
            key={tab.segment}
            href={href}
            className={cn(
              "-mb-px whitespace-nowrap border-b-2 px-3 py-2 text-sm",
              active
                ? "border-foreground font-medium text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground"
            )}
          >
            {tab.label}
          </Link>
        )
      })}
    </nav>
  )
}
