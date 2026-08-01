"use client"

import Link from "next/link"
import { useTransition } from "react"
import { useLocale, useTranslations } from "next-intl"

import { signOutAction, switchTenantAction } from "@/actions/auth"
import { updateLocaleAction } from "@/actions/locale"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"
import type { Session, TenantMembership } from "@/lib/auth"
import {
  CheckIcon,
  ChevronsUpDownIcon,
  LanguagesIcon,
  LogOutIcon,
  ShieldCheckIcon,
} from "lucide-react"

type NavUserProps = {
  session: Session
  tenants: TenantMembership[]
}

/** Two-letter fallback for users without an avatar image. */
function initialsOf(name: string | null, email: string): string {
  const source = name?.trim() || email
  const parts = source.split(/[\s@._-]+/).filter(Boolean)
  return parts
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("")
}

export function NavUser({ session, tenants }: NavUserProps) {
  const { isMobile } = useSidebar()
  const t = useTranslations("common")
  const locale = useLocale()
  const [pending, startTransition] = useTransition()

  const { user } = session
  const displayName = user.name?.trim() || user.email
  const initials = initialsOf(user.name, user.email)
  const nextLocale = locale === "de" ? "en" : "de"

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <SidebarMenuButton
                size="lg"
                className="data-open:bg-sidebar-accent data-open:text-sidebar-accent-foreground"
              />
            }
          >
            <Avatar className="h-8 w-8 rounded-lg">
              {user.image && <AvatarImage src={user.image} alt={displayName} />}
              <AvatarFallback className="rounded-lg bg-primary/10 text-xs font-medium text-primary">
                {initials}
              </AvatarFallback>
            </Avatar>
            <div className="grid flex-1 text-start text-sm leading-tight">
              <span className="truncate font-semibold">{displayName}</span>
              <span className="truncate text-xs">{user.email}</span>
            </div>
            <ChevronsUpDownIcon className="ms-auto size-4" />
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="min-w-56 rounded-lg"
            side={isMobile ? "bottom" : "right"}
            align="end"
            sideOffset={4}
          >
            {/* base-ui requires GroupLabel to live inside a Group — unlike
                radix, where a bare label is fine. */}
            <DropdownMenuGroup>
              <DropdownMenuLabel className="p-0 font-normal">
                <div className="flex items-center gap-2 px-1 py-1.5 text-start text-sm">
                  <Avatar className="h-8 w-8 rounded-lg">
                    {user.image && (
                      <AvatarImage src={user.image} alt={displayName} />
                    )}
                    <AvatarFallback className="rounded-lg bg-primary/10 text-xs font-medium text-primary">
                      {initials}
                    </AvatarFallback>
                  </Avatar>
                  <div className="grid flex-1 text-start text-sm leading-tight">
                    <span className="truncate font-semibold">
                      {displayName}
                    </span>
                    <span className="truncate text-xs">{user.email}</span>
                  </div>
                </div>
              </DropdownMenuLabel>
            </DropdownMenuGroup>

            {tenants.length > 1 && (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuGroup>
                  <DropdownMenuLabel className="text-xs text-muted-foreground">
                    {t("switchClub")}
                  </DropdownMenuLabel>
                  {tenants.map((tenant) => (
                    <DropdownMenuItem
                      key={tenant.tenant_id}
                      disabled={pending}
                      onClick={() => {
                        if (tenant.tenant_id === session.tenant_id) return
                        startTransition(async () => {
                          await switchTenantAction(tenant.tenant_id)
                        })
                      }}
                    >
                      <span className="truncate">
                        {tenant.short_name || tenant.name}
                      </span>
                      {tenant.tenant_id === session.tenant_id && (
                        <CheckIcon className="ms-auto size-4" />
                      )}
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuGroup>
              </>
            )}

            {session.is_superuser && !session.impersonator && (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuGroup>
                  <DropdownMenuItem render={<Link href="/admin" />}>
                    <ShieldCheckIcon />
                    {t("adminArea")}
                  </DropdownMenuItem>
                </DropdownMenuGroup>
              </>
            )}

            <DropdownMenuSeparator />
            <DropdownMenuGroup>
              <DropdownMenuItem
                disabled={pending}
                onClick={() =>
                  startTransition(async () => {
                    await updateLocaleAction(nextLocale)
                  })
                }
              >
                <LanguagesIcon />
                {nextLocale === "de" ? t("german") : t("english")}
              </DropdownMenuItem>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={() => startTransition(async () => await signOutAction())}
            >
              <LogOutIcon />
              {t("signOut")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
