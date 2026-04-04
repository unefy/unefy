"use client"

import { useTranslations } from "next-intl"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { SectionHeading } from "@/components/layout/section-heading"
import { useSettingsForm } from "@/components/settings/settings-shell"

function validateFormat(format: string): string | null {
  if (!format.trim()) return "empty"
  if (!format.includes("{NUM")) return "missingNum"

  // Check for invalid variables
  const braceContent = format.match(/\{[^}]*\}/g) || []
  for (const token of braceContent) {
    if (
      token !== "{YEAR}" &&
      !/^\{NUM(:[1-9])?\}$/.test(token)
    ) {
      return "invalidVariable"
    }
  }

  return null
}

function formatMemberNumber(format: string, num: number): string {
  const year = new Date().getFullYear().toString()
  let result = format

  result = result.replace(/\{YEAR\}/g, year)

  const numMatch = result.match(/\{NUM:([1-9])\}/)
  if (numMatch) {
    const pad = parseInt(numMatch[1], 10)
    result = result.replace(/\{NUM:[1-9]\}/g, String(num).padStart(pad, "0"))
  }

  result = result.replace(/\{NUM\}/g, String(num))

  return result || String(num)
}

export function DefaultsForm() {
  const t = useTranslations("settings")
  const { form, handleChange } = useSettingsForm()

  const formatValue = form.member_number_format as string
  const formatError = validateFormat(formatValue)

  return (
    <div className="space-y-10">
      <div>
        <SectionHeading
          title={t("memberNumbers")}
          description={t("memberNumbersDescription")}
        />
        <div className="space-y-4">
          <div className="grid grid-cols-4 gap-4">
            <div className="col-span-2 space-y-2">
              <Label htmlFor="member_number_format">
                {t("memberNumberFormat")}
              </Label>
              <Input
                id="member_number_format"
                value={formatValue}
                onChange={(e) =>
                  handleChange("member_number_format", e.target.value)
                }
                placeholder="ESV-{YEAR}-{NUM:3}"
                aria-invalid={!!formatError}
              />
              {formatError && (
                <p className="text-destructive text-xs">
                  {t(`memberNumberFormatError.${formatError}`)}
                </p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="member_number_next">
                {t("memberNumberNext")}
              </Label>
              <Input
                id="member_number_next"
                type="number"
                min={1}
                value={form.member_number_next as string}
                onKeyDown={(e) => {
                  if (e.key === "-" || e.key === "e" || e.key === "E" || e.key === "+" || e.key === ".") {
                    e.preventDefault()
                  }
                }}
                onChange={(e) => {
                  const val = e.target.value.replace(/[^0-9]/g, "")
                  if (val === "" || parseInt(val, 10) >= 1) {
                    handleChange("member_number_next", val)
                  }
                }}
              />
            </div>
            <div className="space-y-2">
              <Label>{t("memberNumberPreview")}</Label>
              <div className="flex h-9 items-center rounded-3xl bg-input/50 px-3">
                <p className="text-sm font-mono">
                  {formatMemberNumber(
                    form.member_number_format as string,
                    Number(form.member_number_next) || 1,
                  )}
                </p>
              </div>
            </div>
          </div>
          <div className="text-muted-foreground text-xs space-y-0.5">
            <p>{t("memberNumberFormatHelp")}</p>
            <p>{t("memberNumberFormatExample")}</p>
          </div>
        </div>
      </div>
    </div>
  )
}
