"use client"

import { useMemo } from "react"
import { useTranslations } from "next-intl"
import { HugeiconsIcon } from "@hugeicons/react"
import { Add01Icon, Delete02Icon, LockPasswordIcon } from "@hugeicons/core-free-icons"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { SectionHeading } from "@/components/layout/section-heading"
import { useSettingsForm } from "@/components/settings/settings-shell"
import { useClub } from "@/hooks/use-club"
import {
  parseMemberStatuses,
  slugifyStatusKey,
  STATUS_TRANSLATIONS,
  type MemberStatusOption,
} from "@/lib/types/club"

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
  const tm = useTranslations("members")
  const { form, handleChange } = useSettingsForm()
  const { data: club } = useClub()

  const formatValue = form.member_number_format as string
  const formatError = validateFormat(formatValue)

  const statuses = useMemo(
    () =>
      parseMemberStatuses(
        (form.member_statuses as string | null | undefined) || null,
      ),
    [form.member_statuses],
  )

  // Keys that have already been persisted to the backend. Their keys are
  // frozen — renaming the label does NOT change the key, to avoid orphaning
  // member records that reference them.
  const persistedKeys = useMemo(() => {
    const persisted = parseMemberStatuses(club?.member_statuses ?? null)
    return new Set(persisted.map((s) => s.key))
  }, [club?.member_statuses])

  function updateStatuses(next: MemberStatusOption[]) {
    handleChange("member_statuses", JSON.stringify(next))
  }

  function addStatus() {
    // Use a random temporary key so it never collides with real keys. It will
    // be replaced as soon as the user types a label (see updateCustomLabel).
    const tempKey = `_new_${Math.random().toString(36).slice(2, 8)}`
    updateStatuses([...statuses, { key: tempKey, label: "" }])
  }

  function removeStatus(index: number) {
    updateStatuses(statuses.filter((_, i) => i !== index))
  }

  function updateCustomLabel(index: number, value: string) {
    const status = statuses[index]
    if (!status) return
    // Freeze the key once the status has been persisted — renaming the label
    // must not reassign the key of already-saved statuses.
    const isPersisted = persistedKeys.has(status.key)
    let nextKey = status.key
    if (!isPersisted) {
      const existingKeys = new Set(
        statuses.filter((_, i) => i !== index).map((s) => s.key),
      )
      const base = slugifyStatusKey(value)
      nextKey = base
      let suffix = 1
      while (existingKeys.has(nextKey)) {
        nextKey = `${base}_${suffix++}`
      }
    }
    updateStatuses(
      statuses.map((s, i) =>
        i === index ? { ...s, label: value, key: nextKey } : s,
      ),
    )
  }

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
                <p className="text-sm">
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

      <div>
        <SectionHeading
          title={t("memberStatuses")}
          description={t("memberStatusesDescription")}
        />
        <div className="max-w-sm space-y-2">
          {statuses.map((status, index) => {
            const translationKey = STATUS_TRANSLATIONS[status.key]
            const displayLabel = translationKey
              ? tm(translationKey)
              : status.label

            return (
              <div
                key={`${status.key}-${index}`}
                className="flex items-center gap-3"
              >
                {translationKey ? (
                  <div className="flex h-9 flex-1 items-center rounded-3xl bg-input/50 px-4">
                    <span className="text-sm text-muted-foreground">{displayLabel}</span>
                  </div>
                ) : (
                  <Input
                    value={status.label}
                    onChange={(e) => updateCustomLabel(index, e.target.value)}
                    placeholder={t("statusLabelPlaceholder")}
                    className="flex-1"
                  />
                )}
                {translationKey ? (
                  <div
                    className="flex size-9 items-center justify-center text-muted-foreground"
                    aria-label={t("systemEntry")}
                    title={t("systemEntry")}
                  >
                    <HugeiconsIcon icon={LockPasswordIcon} size={16} />
                  </div>
                ) : (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => removeStatus(index)}
                    aria-label={t("removeStatus")}
                  >
                    <HugeiconsIcon icon={Delete02Icon} size={16} />
                  </Button>
                )}
              </div>
            )
          })}
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={addStatus}
          >
            <HugeiconsIcon icon={Add01Icon} size={16} />
            {t("addStatus")}
          </Button>
          <p className="text-muted-foreground text-xs pt-2">
            {t("memberStatusesHelp")}
          </p>
        </div>
      </div>
    </div>
  )
}
