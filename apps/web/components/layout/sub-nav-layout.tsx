"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"

interface SubNavItem {
  label: string
  href: string
}

interface SubNavLayoutProps {
  items: SubNavItem[]
  children: React.ReactNode
}

export function SubNavLayout({ items, children }: SubNavLayoutProps) {
  const pathname = usePathname()

  return (
    <div className="flex gap-16">
      <nav className="w-48 shrink-0 space-y-1">
        {items.map((item) => {
          // Exact match for the first item (root), startsWith for the rest
          const isFirst = item.href === items[0]?.href
          const isActive = isFirst
            ? pathname === item.href
            : pathname.startsWith(item.href)

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "block w-full rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground hover:bg-accent/50 hover:text-foreground",
              )}
            >
              {item.label}
            </Link>
          )
        })}
      </nav>
      <div className="flex-1 max-w-2xl">{children}</div>
    </div>
  )
}
