"use client"

import { useRouter } from "next/navigation"
import { useEffect, useRef, useState } from "react"
import { useTranslations } from "next-intl"
import { HugeiconsIcon } from "@hugeicons/react"
import { ArrowDown01Icon, Search01Icon } from "@hugeicons/core-free-icons"

import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { useMembers } from "@/hooks/use-members"
import { useDebounce } from "@/hooks/use-debounce"
import { cn } from "@/lib/utils"

interface MemberSwitcherProps {
  currentId: string
  currentLabel: string
}

const LISTBOX_ID = "member-switcher-list"

export function MemberSwitcher({ currentId, currentLabel }: MemberSwitcherProps) {
  const t = useTranslations("members")
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const [activeIndex, setActiveIndex] = useState(0)
  const listRef = useRef<HTMLUListElement>(null)
  const search = useDebounce(query, 200)

  const { data, isLoading } = useMembers({
    search: search || undefined,
    per_page: 20,
  })
  const members = data?.data ?? []

  // Reset active index when the result set changes
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setActiveIndex(0)
  }, [search])

  // Scroll the active item into view when it changes
  useEffect(() => {
    const item = listRef.current?.querySelector<HTMLElement>(
      `[data-index="${activeIndex}"]`,
    )
    item?.scrollIntoView({ block: "nearest" })
  }, [activeIndex])

  function select(id: string) {
    setOpen(false)
    setQuery("")
    if (id !== currentId) {
      router.push(`/members/${id}`)
    }
  }

  function handleOpenChange(next: boolean) {
    setOpen(next)
    if (!next) {
      setQuery("")
      setActiveIndex(0)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (members.length === 0) return
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault()
        setActiveIndex((i) => Math.min(i + 1, members.length - 1))
        break
      case "ArrowUp":
        e.preventDefault()
        setActiveIndex((i) => Math.max(i - 1, 0))
        break
      case "Home":
        e.preventDefault()
        setActiveIndex(0)
        break
      case "End":
        e.preventDefault()
        setActiveIndex(members.length - 1)
        break
      case "Enter": {
        e.preventDefault()
        const target = members[activeIndex]
        if (target) select(target.id)
        break
      }
    }
  }

  const activeOptionId =
    members[activeIndex] !== undefined
      ? `member-switcher-option-${activeIndex}`
      : undefined

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger
        render={
          <button
            type="button"
            aria-label={t("switchMember")}
            className="group/switcher -mx-2 -my-1 inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-left transition-colors hover:bg-muted focus-visible:bg-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring data-[popup-open]:bg-muted"
          />
        }
      >
        <h1 className="whitespace-nowrap text-2xl font-bold tracking-tight">
          {currentLabel}
        </h1>
        <HugeiconsIcon
          icon={ArrowDown01Icon}
          size={16}
          className="shrink-0 text-muted-foreground transition-transform group-data-[popup-open]/switcher:rotate-180"
        />
      </PopoverTrigger>
      <PopoverContent
        align="start"
        sideOffset={6}
        className="w-80 gap-0 p-0"
      >
        <div className="flex items-center gap-2 border-b border-border px-3 py-2">
          <HugeiconsIcon
            icon={Search01Icon}
            size={14}
            className="shrink-0 text-muted-foreground"
          />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t("searchPlaceholder")}
            autoFocus
            role="combobox"
            aria-expanded="true"
            aria-controls={LISTBOX_ID}
            aria-activedescendant={activeOptionId}
            aria-autocomplete="list"
            className="h-8 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          />
        </div>
        <ul
          ref={listRef}
          id={LISTBOX_ID}
          role="listbox"
          className="max-h-72 overflow-y-auto p-1"
          aria-label={t("title")}
        >
          {isLoading ? (
            <li className="px-3 py-2 text-sm text-muted-foreground">
              {t("loading")}
            </li>
          ) : members.length === 0 ? (
            <li className="px-3 py-6 text-center text-sm text-muted-foreground">
              {t("noResults")}
            </li>
          ) : (
            members.map((m, i) => {
              const isCurrent = m.id === currentId
              const isActive = i === activeIndex
              return (
                <li key={m.id}>
                  <div
                    id={`member-switcher-option-${i}`}
                    role="option"
                    aria-selected={isCurrent}
                    data-index={i}
                    onMouseEnter={() => setActiveIndex(i)}
                    onClick={() => select(m.id)}
                    className={cn(
                      "flex cursor-pointer items-center justify-between gap-2 rounded-lg px-3 py-2 text-left text-sm transition-colors",
                      isActive && "bg-accent",
                      isCurrent && !isActive && "bg-accent/50",
                    )}
                  >
                    <span className="truncate">
                      {m.first_name} {m.last_name}
                    </span>
                    <span className="shrink-0 text-xs text-muted-foreground">
                      {m.member_number}
                    </span>
                  </div>
                </li>
              )
            })
          )}
        </ul>
      </PopoverContent>
    </Popover>
  )
}
