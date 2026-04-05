"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useEffect, useState } from "react"
import { cn } from "@/lib/utils"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Home03Icon,
  UserGroupIcon,
  Calendar03Icon,
  Invoice02Icon,
  Settings02Icon,
  Logout03Icon,
  UserCircleIcon,
  ArrowDown01Icon,
  LanguageSquareIcon,
} from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"
import { useTranslations, useLocale } from "next-intl"
import { useRouter } from "next/navigation"
import { API_URL } from "@/lib/constants"

interface AppSidebarProps {
  user: {
    id: string
    name: string
    email: string
    image?: string | null
  }
  tenantName?: string
}

const navigationItems = [
  { key: "dashboard" as const, href: "/", icon: Home03Icon },
  { key: "members" as const, href: "/members", icon: UserGroupIcon },
  { key: "events" as const, href: "/events", icon: Calendar03Icon },
  { key: "dues" as const, href: "/dues", icon: Invoice02Icon },
  { key: "settings" as const, href: "/settings", icon: Settings02Icon },
]

const MOBILE_BREAKPOINT = 768

export function AppSidebar({ user, tenantName = "My Club" }: AppSidebarProps) {
  const pathname = usePathname()
  const router = useRouter()
  const t = useTranslations()
  const locale = useLocale()
  const [collapsed, setCollapsed] = useState(false)

  useEffect(() => {
    function handleResize() {
      setCollapsed(window.innerWidth < MOBILE_BREAKPOINT)
    }
    handleResize()
    window.addEventListener("resize", handleResize)
    return () => window.removeEventListener("resize", handleResize)
  }, [])

  async function handleSignOut() {
    await fetch(`${API_URL}/api/v1/auth/logout`, {
      method: "POST",
      credentials: "include",
    })
    window.location.href = "/login"
  }

  return (
    <TooltipProvider delay={0}>
      <aside
        className={cn(
          "flex shrink-0 flex-col bg-card transition-all duration-200",
          collapsed ? "w-[60px]" : "w-64",
        )}
      >
        {/* Tenant switcher */}
        <div className="p-2">
          <DropdownMenu>
            <DropdownMenuTrigger
              className={cn(
                "flex w-full items-center gap-3 rounded-lg bg-muted/50 transition-colors hover:bg-muted cursor-pointer",
                collapsed ? "justify-center p-2" : "px-3 py-2",
              )}
            >
              <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded bg-primary text-primary-foreground text-[10px] font-bold">
                {tenantName.charAt(0).toUpperCase()}
              </div>
              {!collapsed && (
                <>
                  <div className="min-w-0 flex-1 text-left">
                    <p className="truncate text-sm font-semibold leading-tight">
                      {tenantName}
                    </p>
                    <p className="text-muted-foreground truncate text-[11px] leading-tight mt-0.5">
                      {t("tenant.freePlan")}
                    </p>
                  </div>
                  <HugeiconsIcon
                    icon={ArrowDown01Icon}
                    size={14}
                    className="text-muted-foreground shrink-0"
                  />
                </>
              )}
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              <DropdownMenuItem disabled>
                <span className="truncate font-medium">{tenantName}</span>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem disabled>
                <span className="text-muted-foreground text-xs">
                  {t("common.switchClub")}
                </span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {/* Navigation */}
        <div className="flex-1 px-3 pt-3">
          {navigationItems.map((item) => {
            const isActive =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href)

            const linkEl = (
              <Link
                href={item.href}
                className={cn(
                  "flex items-center gap-2.5 rounded-lg text-sm font-medium transition-colors",
                  isActive
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:bg-accent/50 hover:text-foreground",
                  collapsed ? "justify-center p-2.5" : "pl-3.5 pr-2.5 py-2.5",
                )}
              >
                <HugeiconsIcon
                  icon={item.icon}
                  size={20}
                  className="shrink-0"
                  strokeWidth={isActive ? 2 : 1.5}
                />
                {!collapsed && <span>{t(`nav.${item.key}`)}</span>}
              </Link>
            )

            return (
              <div key={item.href} className="mb-0.5">
                {collapsed ? (
                  <Tooltip>
                    <TooltipTrigger>{linkEl}</TooltipTrigger>
                    <TooltipContent side="right">{t(`nav.${item.key}`)}</TooltipContent>
                  </Tooltip>
                ) : (
                  linkEl
                )}
              </div>
            )
          })}
        </div>

        {/* User */}
        <div className="p-2">
          <DropdownMenu>
            <DropdownMenuTrigger
              className={cn(
                "flex w-full items-center gap-3 rounded-lg bg-muted/50 transition-colors hover:bg-muted cursor-pointer",
                collapsed ? "justify-center p-2" : "px-3 py-2",
              )}
            >
              {user.image ? (
                // OAuth provider avatars (Google) — small, already optimized.
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={user.image}
                  alt={user.name}
                  className="h-8 w-8 shrink-0 rounded-full"
                />
              ) : (
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted">
                  <HugeiconsIcon
                    icon={UserCircleIcon}
                    size={20}
                    className="text-muted-foreground"
                  />
                </div>
              )}
              {!collapsed && (
                <div className="flex-1 overflow-hidden text-left">
                  <p className="truncate text-sm font-medium leading-tight">
                    {user.name}
                  </p>
                </div>
              )}
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="start"
              side="top"
              sideOffset={8}
              className=""
            >
              <div className="px-2 py-1.5">
                <p className="text-sm font-medium">{user.name}</p>
                <p className="text-muted-foreground text-xs break-all">{user.email}</p>
              </div>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={async () => {
                  const next = locale === "de" ? "en" : "de"
                  document.cookie = `locale=${next};path=/;max-age=${60 * 60 * 24 * 365}`
                  // Persist to backend (fire-and-forget)
                  fetch(`${API_URL}/api/v1/auth/me/locale`, {
                    method: "PATCH",
                    headers: { "Content-Type": "application/json" },
                    credentials: "include",
                    body: JSON.stringify({ locale: next }),
                  })
                  router.refresh()
                }}
              >
                <HugeiconsIcon icon={LanguageSquareIcon} size={16} className="mr-2" />
                {locale === "de" ? t("common.english") : t("common.german")}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={handleSignOut}>
                <HugeiconsIcon icon={Logout03Icon} size={16} className="mr-2" />
                {t("common.signOut")}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </aside>
    </TooltipProvider>
  )
}
