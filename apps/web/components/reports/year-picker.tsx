"use client"

import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

/**
 * Which year the report covers.
 *
 * The years come from the backend rather than being counted off from today:
 * it knows when the club's first member joined and where its own calendar
 * stands, and a picker offering a year with nothing in it is a page nobody can
 * explain.
 */
export function YearPicker({ year, years }: { year: number; years: number[] }) {
  const router = useRouter()
  const t = useTranslations("reports")

  return (
    <Select
      value={String(year)}
      onValueChange={(value) => {
        // A navigation rather than local state: the figures are server-read,
        // and the chosen year belongs in the URL so it survives a reload and
        // can be sent to the treasurer as a link.
        router.push(`/reports?year=${value}`)
      }}
    >
      <SelectTrigger aria-label={t("year")}>
        <SelectValue>{(value: string) => value}</SelectValue>
      </SelectTrigger>
      <SelectContent>
        {years.map((option) => (
          <SelectItem key={option} value={String(option)}>
            {option}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
