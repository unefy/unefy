"use client"

import { useEffect, useMemo, useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"

import { searchMembersAction } from "@/actions/attendance"
import {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "@/components/ui/command"
import { sidebarData } from "@/components/layout/sidebar-data"
import type { Member } from "@/lib/types/member"
import { UserIcon } from "lucide-react"

/** Below this a member search is more noise than help. */
const MIN_SEARCH = 2

/**
 * Cmd/Ctrl+K — go anywhere, find anyone.
 *
 * Navigation comes from the same `sidebarData` the sidebar renders, so a page
 * can never be reachable in one and missing from the other. Members are
 * searched on the server, because the register is larger than one page and the
 * point of this box is to reach member 240 without scrolling to them.
 */
export function CommandPalette({
  role,
  modules,
}: {
  role: string | null
  modules: string[]
}) {
  const t = useTranslations("commandPalette")
  const tNav = useTranslations("nav")
  const router = useRouter()

  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState("")
  const [members, setMembers] = useState<Member[]>([])
  const [, startTransition] = useTransition()

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "k" && (event.metaKey || event.ctrlKey)) {
        event.preventDefault()
        setOpen((current) => !current)
      }
    }
    document.addEventListener("keydown", onKeyDown)
    return () => document.removeEventListener("keydown", onKeyDown)
  }, [])

  // Debounced: somebody types a name, not a query per keystroke.
  useEffect(() => {
    const term = search.trim()
    if (term.length < MIN_SEARCH) return
    const handle = setTimeout(() => {
      startTransition(async () => {
        const result = await searchMembersAction(term)
        setMembers(result.success ? (result.data ?? []) : [])
      })
    }, 200)
    return () => clearTimeout(handle)
  }, [search])

  // Whether the last answer still applies is derived from the term rather than
  // cleared in the effect: a short term simply shows no member rows, and the
  // results reappear without a second request when it grows again.
  const visibleMembers =
    search.trim().length >= MIN_SEARCH ? members : []

  // The same visibility rules the sidebar applies — role and active modules.
  const destinations = useMemo(() => {
    const visible = (item: { module?: string; roles?: string[] }) =>
      (!item.module || modules.includes(item.module)) &&
      (!item.roles || (role !== null && item.roles.includes(role)))

    return sidebarData.navGroups.flatMap((group) =>
      group.items.filter(visible).flatMap((item) =>
        item.items && item.items.length > 0
          ? item.items.map((child) => ({
              key: `${item.titleKey}.${child.titleKey}`,
              label: `${tNav(item.titleKey)} · ${tNav(child.titleKey)}`,
              url: child.url,
            }))
          : [{ key: item.titleKey, label: tNav(item.titleKey), url: item.url }]
      )
    )
  }, [modules, role, tNav])

  function go(url: string) {
    setOpen(false)
    setSearch("")
    router.push(url)
  }

  return (
    <CommandDialog
      open={open}
      onOpenChange={setOpen}
      title={t("title")}
      description={t("description")}
    >
      {/*
        `shouldFilter={false}` for the member half: those rows are already the
        server's answer to the term, and filtering them again locally would
        drop hits that matched on a field not shown in the row.
      */}
      <Command shouldFilter={false}>
        <CommandInput
          value={search}
          onValueChange={setSearch}
          placeholder={t("placeholder")}
        />
        <CommandList>
          <CommandEmpty>{t("empty")}</CommandEmpty>

          <CommandGroup heading={t("groups.navigate")}>
            {destinations
              .filter((destination) =>
                destination.label
                  .toLowerCase()
                  .includes(search.trim().toLowerCase())
              )
              .map((destination) => (
                <CommandItem
                  key={destination.key}
                  value={destination.key}
                  onSelect={() => go(destination.url)}
                >
                  {destination.label}
                  <CommandShortcut>{destination.url}</CommandShortcut>
                </CommandItem>
              ))}
          </CommandGroup>

          {visibleMembers.length > 0 && (
            <>
              <CommandSeparator />
              <CommandGroup heading={t("groups.members")}>
                {visibleMembers.map((member) => (
                  <CommandItem
                    key={member.id}
                    value={member.id}
                    onSelect={() => go(`/members/${member.id}`)}
                  >
                    <UserIcon />
                    {member.first_name} {member.last_name}
                    {member.member_number && (
                      <CommandShortcut>{member.member_number}</CommandShortcut>
                    )}
                  </CommandItem>
                ))}
              </CommandGroup>
            </>
          )}
        </CommandList>
      </Command>
    </CommandDialog>
  )
}
