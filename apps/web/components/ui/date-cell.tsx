"use client"

import { useLocale } from "next-intl"

import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"

/**
 * A date in a table cell: the compact date is shown, the exact timestamp sits
 * in a tooltip. Tables stay scannable without losing the precision that
 * matters when reconstructing what happened.
 *
 * `dateOnly` is for values the backend stores as a plain date (a joining date,
 * a founding date) — there the time would be a meaningless midnight.
 */
export function DateCell({
  value,
  dateOnly = false,
}: {
  value: string | null | undefined
  dateOnly?: boolean
}) {
  const locale = useLocale()
  if (!value) return <span className="text-muted-foreground">—</span>

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return <span className="text-muted-foreground">—</span>
  }

  const short = new Intl.DateTimeFormat(locale, { dateStyle: "medium" }).format(
    date
  )

  if (dateOnly) return <>{short}</>

  const full = new Intl.DateTimeFormat(locale, {
    dateStyle: "full",
    timeStyle: "medium",
  }).format(date)

  return (
    <Tooltip>
      {/* No underline: the tooltip is a bonus, not something the cell should
          advertise. `cursor-help` is the only hint, and it costs no pixels. */}
      <TooltipTrigger render={<span className="cursor-help" />}>
        {short}
      </TooltipTrigger>
      <TooltipContent>{full}</TooltipContent>
    </Tooltip>
  )
}
