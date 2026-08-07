"use client"

import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"

import { DateCell } from "@/components/ui/date-cell"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { FunctionHolder } from "@/lib/types/functions"

/**
 * The board list: who holds which office at the chosen date. Changing the
 * date navigates — the date lives in the URL, so a specific year's board can
 * be linked and reloaded.
 */
export function FunctionHolders({
  holders,
  at,
  hasDivisions,
}: {
  holders: FunctionHolder[]
  /** The effective reference date (today when none was chosen). */
  at: string
  hasDivisions: boolean
}) {
  const t = useTranslations("functionHolders")
  const router = useRouter()

  return (
    <>
      <div className="flex items-end gap-2">
        <div className="space-y-2">
          <Label htmlFor="holders-at">{t("date")}</Label>
          <Input
            id="holders-at"
            type="date"
            value={at}
            onChange={(e) => {
              if (e.target.value) {
                router.push(`/functions?at=${e.target.value}`)
              }
            }}
            className="w-fit"
          />
        </div>
      </div>

      {holders.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("empty")}</p>
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("columns.function")}</TableHead>
                {hasDivisions && (
                  <TableHead>{t("columns.division")}</TableHead>
                )}
                <TableHead>{t("columns.member")}</TableHead>
                <TableHead>{t("columns.since")}</TableHead>
                <TableHead>{t("columns.until")}</TableHead>
                <TableHead>{t("columns.note")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {holders.map((holder) => (
                <TableRow key={holder.assignment_id}>
                  <TableCell className="font-medium">
                    {holder.function_name}
                  </TableCell>
                  {hasDivisions && (
                    <TableCell className="text-muted-foreground">
                      {holder.division_name ?? "—"}
                    </TableCell>
                  )}
                  <TableCell>
                    {holder.member_first_name} {holder.member_last_name}
                  </TableCell>
                  <TableCell>
                    <DateCell value={holder.valid_from} dateOnly />
                  </TableCell>
                  <TableCell>
                    {holder.valid_to ? (
                      <DateCell value={holder.valid_to} dateOnly />
                    ) : (
                      <span className="text-muted-foreground">
                        {t("ongoing")}
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {holder.note ?? "—"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </>
  )
}
