"use client"

import { useEffect, useState, useTransition } from "react"
import { useTranslations } from "next-intl"

import { searchMembersAction } from "@/actions/attendance"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import type { Member } from "@/lib/types/member"
import { SearchIcon } from "lucide-react"

/**
 * Type-to-find member picker.
 *
 * Searches on the server instead of filtering a preloaded list: a page caps at
 * 100 members, and the supervisor has to be able to find member 240 too.
 */
export function MemberSearch({
  onSelect,
  placeholder,
  /** Members already on the list — shown, but not selectable twice. */
  takenIds = [],
  takenLabel,
  disabled = false,
  actionLabel,
}: {
  onSelect: (member: Member) => void
  placeholder: string
  takenIds?: string[]
  takenLabel?: string
  disabled?: boolean
  actionLabel: string
}) {
  const t = useTranslations("attendance.search")
  const [term, setTerm] = useState("")
  const [results, setResults] = useState<Member[]>([])
  const [searched, setSearched] = useState(false)
  const [, startTransition] = useTransition()

  // Whether a search is meaningful is derived from the term, not mirrored
  // into state — one less thing that can disagree with the input.
  const active = term.trim().length >= 2

  useEffect(() => {
    if (!active) return
    // Debounced: the supervisor types a name, not a query per keystroke.
    const handle = setTimeout(() => {
      startTransition(async () => {
        const result = await searchMembersAction(term)
        setResults(result.success ? (result.data ?? []) : [])
        setSearched(true)
      })
    }, 250)
    return () => clearTimeout(handle)
  }, [term, active])

  return (
    <div className="space-y-2">
      <div className="relative">
        <SearchIcon className="pointer-events-none absolute start-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={term}
          disabled={disabled}
          onChange={(event) => setTerm(event.target.value)}
          placeholder={placeholder}
          className="ps-9"
          aria-label={placeholder}
        />
      </div>

      {active && searched && results.length === 0 && (
        <p className="text-sm text-muted-foreground">{t("noResults")}</p>
      )}

      {active && results.length > 0 && (
        <ul className="divide-y rounded-md border">
          {results.map((member) => {
            const taken = takenIds.includes(member.id)
            return (
              <li
                key={member.id}
                className="flex items-center justify-between gap-3 px-3 py-2"
              >
                <span className="min-w-0 text-sm">
                  <span className="font-medium">
                    {member.last_name}, {member.first_name}
                  </span>{" "}
                  <span className="font-mono text-xs text-muted-foreground">
                    {member.member_number}
                  </span>
                </span>
                {taken ? (
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {takenLabel}
                  </span>
                ) : (
                  <Button
                    type="button"
                    size="sm"
                    disabled={disabled}
                    onClick={() => {
                      onSelect(member)
                      setTerm("")
                      setResults([])
                      setSearched(false)
                    }}
                  >
                    {actionLabel}
                  </Button>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
