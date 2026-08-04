"use client"

import { useState } from "react"
import { useTranslations } from "next-intl"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { DownloadIcon } from "lucide-react"

function firstOfYear(): string {
  return `${new Date().getFullYear()}-01-01`
}

function today(): string {
  return new Date().toISOString().slice(0, 10)
}

/**
 * Standbuch download. A plain navigation to the proxy route rather than an
 * action — a server action cannot answer with a file.
 */
export function RangeBookExport() {
  const t = useTranslations("shooting.rangeBook")
  const [from, setFrom] = useState(firstOfYear)
  const [to, setTo] = useState(today)

  const valid = from !== "" && to !== "" && from <= to
  const href = `/api/shooting/range-book?from=${from}&to=${to}`

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("title")}</CardTitle>
        <CardDescription>{t("hint")}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap items-end gap-3">
          <div className="space-y-2">
            <Label htmlFor="range-book-from">{t("from")}</Label>
            <Input
              id="range-book-from"
              type="date"
              value={from}
              onChange={(event) => setFrom(event.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="range-book-to">{t("to")}</Label>
            <Input
              id="range-book-to"
              type="date"
              value={to}
              onChange={(event) => setTo(event.target.value)}
            />
          </div>
          <Button
            disabled={!valid}
            render={
              // Navigation, not fetch: the browser handles the download.
              <a href={valid ? href : undefined} download>
                <DownloadIcon />
                {t("download")}
              </a>
            }
          />
        </div>
      </CardContent>
    </Card>
  )
}
