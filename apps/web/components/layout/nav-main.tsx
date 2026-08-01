"use client"

import { useState, type ReactNode } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { useTranslations } from "next-intl"

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
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
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  useSidebar,
} from "@/components/ui/sidebar"
import type { NavGroup, NavItem } from "@/components/layout/sidebar-data"
import { ChevronRightIcon } from "lucide-react"

export function NavMain({
  navGroups,
  namespace = "nav",
}: {
  navGroups: NavGroup[]
  /** i18n namespace the `titleKey`s resolve against — the admin area uses its own. */
  namespace?: string
}) {
  return (
    <>
      {navGroups.map((group) => (
        <NavGroupSection
          key={group.titleKey}
          group={group}
          namespace={namespace}
        />
      ))}
    </>
  )
}

function NavBadge({ children }: { children: ReactNode }) {
  return (
    <span className="ml-auto rounded-full bg-primary/10 px-1.5 py-0 text-xs font-medium text-primary">
      {children}
    </span>
  )
}

function checkIsActive(pathname: string, item: NavItem, mainNav = false) {
  const p = pathname.split("?")[0]

  // The dashboard lives at the root, so it must match exactly — a prefix
  // check would light it up on every route.
  if (item.url === "/") return p === "/"

  return (
    p === item.url ||
    !!item.items?.some((i) => i.url === p) ||
    (mainNav &&
      p.split("/")[1] !== "" &&
      p.split("/")[1] === item.url.split("/")[1])
  )
}

function NavGroupSection({
  group,
  namespace,
}: {
  group: NavGroup
  namespace: string
}) {
  const pathname = usePathname()
  const t = useTranslations(namespace)
  const { state, isMobile, setOpenMobile } = useSidebar()
  const isCollapsed = state === "collapsed" && !isMobile

  return (
    <SidebarGroup className="py-1">
      <SidebarGroupLabel>{t(group.titleKey)}</SidebarGroupLabel>
      <SidebarMenu>
        {group.items.map((item) => {
          const key = `${item.titleKey}-${item.url}`
          const title = t(item.titleKey)

          if (!item.items?.length) {
            return (
              <SidebarMenuItem key={key}>
                <SidebarMenuButton
                  isActive={checkIsActive(pathname, item)}
                  tooltip={title}
                  render={
                    <Link
                      href={item.url}
                      onClick={() => setOpenMobile(false)}
                    />
                  }
                >
                  {item.icon && <item.icon />}
                  <span>{title}</span>
                  {item.badge && <NavBadge>{item.badge}</NavBadge>}
                </SidebarMenuButton>
              </SidebarMenuItem>
            )
          }

          const isActive = checkIsActive(pathname, item, true)

          // Collapsed to icons: submenus become a dropdown, since there is no
          // room to expand them inline.
          if (isCollapsed) {
            return (
              <SidebarMenuItem key={key}>
                <DropdownMenu>
                  <DropdownMenuTrigger
                    render={
                      <SidebarMenuButton isActive={isActive} tooltip={title} />
                    }
                  >
                    {item.icon && <item.icon />}
                    <span>{title}</span>
                    {item.badge && <NavBadge>{item.badge}</NavBadge>}
                    <ChevronRightIcon className="ml-auto" />
                  </DropdownMenuTrigger>
                  <DropdownMenuContent
                    className="min-w-56"
                    side="right"
                    align="start"
                    sideOffset={4}
                  >
                    {/* base-ui requires GroupLabel to live inside a Group —
                        unlike radix, where a bare label is fine. */}
                    <DropdownMenuGroup>
                      <DropdownMenuLabel>
                        {title} {item.badge ? `(${item.badge})` : ""}
                      </DropdownMenuLabel>
                      <DropdownMenuSeparator />
                      {item.items.map((sub) => (
                        <DropdownMenuItem
                          key={sub.url}
                          render={
                            <Link
                              href={sub.url}
                              className={
                                pathname === sub.url ? "bg-secondary" : ""
                              }
                            />
                          }
                        >
                          <span className="max-w-52 text-wrap">
                            {t(sub.titleKey)}
                          </span>
                        </DropdownMenuItem>
                      ))}
                    </DropdownMenuGroup>
                  </DropdownMenuContent>
                </DropdownMenu>
              </SidebarMenuItem>
            )
          }

          // Expanded: submenus expand inline.
          return (
            <NavCollapsibleItem
              key={key}
              item={item}
              title={title}
              isActive={isActive}
              namespace={namespace}
            />
          )
        })}
      </SidebarMenu>
    </SidebarGroup>
  )
}

/**
 * Submenu that expands inline. Open state is controlled so navigating into the
 * group can reopen it — an uncontrolled `defaultOpen` would silently change
 * after mount, since the item stays mounted across route changes.
 */
function NavCollapsibleItem({
  item,
  title,
  isActive,
  namespace,
}: {
  item: NavItem
  title: string
  isActive: boolean
  namespace: string
}) {
  const pathname = usePathname()
  const t = useTranslations(namespace)
  const { setOpenMobile } = useSidebar()
  const [open, setOpen] = useState(isActive)
  const [wasActive, setWasActive] = useState(isActive)

  // Adjust during render instead of in an effect: navigating into the group
  // opens it, while a manual toggle survives until the next route change.
  if (isActive !== wasActive) {
    setWasActive(isActive)
    if (isActive) setOpen(true)
  }

  return (
    <Collapsible
      open={open}
      onOpenChange={setOpen}
      className="group/collapsible"
      render={<SidebarMenuItem />}
    >
      <CollapsibleTrigger render={<SidebarMenuButton tooltip={title} />}>
        {item.icon && <item.icon />}
        <span>{title}</span>
        {item.badge && <NavBadge>{item.badge}</NavBadge>}
        <ChevronRightIcon className="ml-auto transition-transform duration-200 group-data-open/collapsible:rotate-90" />
      </CollapsibleTrigger>
      <CollapsibleContent>
        <SidebarMenuSub>
          {item.items?.map((sub) => (
            <SidebarMenuSubItem key={sub.url}>
              <SidebarMenuSubButton
                isActive={pathname === sub.url}
                render={
                  <Link href={sub.url} onClick={() => setOpenMobile(false)} />
                }
              >
                {t(sub.titleKey)}
              </SidebarMenuSubButton>
            </SidebarMenuSubItem>
          ))}
        </SidebarMenuSub>
      </CollapsibleContent>
    </Collapsible>
  )
}
