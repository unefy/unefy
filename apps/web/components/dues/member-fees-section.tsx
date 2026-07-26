"use client"

import { useState } from "react"
import { useTranslations, useLocale } from "next-intl"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { DatePicker } from "@/components/ui/date-picker"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { SectionHeading } from "@/components/layout/section-heading"
import {
  useAssignFee,
  useFeeTypes,
  useMemberFees,
  useRemoveAssignment,
} from "@/hooks/use-dues"
import { useErrorMessage } from "@/lib/errors"
import { formatCurrency } from "@/lib/currency"
import { formatDate } from "@/lib/date"
import { HugeiconsIcon } from "@hugeicons/react"
import { Delete02Icon } from "@hugeicons/core-free-icons"

interface MemberFeesSectionProps {
  memberId: string
}

export function MemberFeesSection({ memberId }: MemberFeesSectionProps) {
  const t = useTranslations("dues")
  const tc = useTranslations("common")
  const locale = useLocale()
  const getErrorMessage = useErrorMessage()

  const { data: assignments, isLoading } = useMemberFees(memberId)
  const { data: feeTypes } = useFeeTypes()
  const assignFee = useAssignFee()
  const removeAssignment = useRemoveAssignment()

  const [feeTypeId, setFeeTypeId] = useState("")
  const [validFrom, setValidFrom] = useState("")

  const feeTypeById = new Map((feeTypes ?? []).map((f) => [f.id, f]))
  const feeTypeItems = (feeTypes ?? []).map((f) => ({
    value: f.id,
    label: `${f.name} (${formatCurrency(f.amount, locale)})`,
  }))

  function handleAssign() {
    if (!feeTypeId || !validFrom) return
    assignFee.mutate(
      { member_id: memberId, fee_type_id: feeTypeId, valid_from: validFrom },
      {
        onSuccess: () => {
          toast.success(tc("saved"))
          setFeeTypeId("")
          setValidFrom("")
        },
        onError: (err) => toast.error(getErrorMessage(err)),
      },
    )
  }

  function handleRemove(id: string) {
    removeAssignment.mutate(
      { id, memberId },
      {
        onSuccess: () => toast.success(tc("saved")),
        onError: (err) => toast.error(getErrorMessage(err)),
      },
    )
  }

  return (
    <div className="space-y-8">
      <div>
        <SectionHeading title={t("memberFees")} description="" />
        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 2 }).map((_, i) => (
              <div key={i} className="h-12 animate-pulse rounded-lg bg-muted" />
            ))}
          </div>
        ) : !assignments || assignments.length === 0 ? (
          <p className="text-muted-foreground text-sm">{t("noMemberFees")}</p>
        ) : (
          <div className="space-y-2">
            {assignments.map((assignment) => {
              const feeType = feeTypeById.get(assignment.fee_type_id)
              return (
                <div
                  key={assignment.id}
                  className="flex items-center justify-between rounded-lg border px-3 py-2"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">
                      {feeType?.name ?? t("unknownFeeType")}
                      {feeType && (
                        <span className="text-muted-foreground ml-2 font-normal">
                          {formatCurrency(feeType.amount, locale)}
                        </span>
                      )}
                    </p>
                    <p className="text-muted-foreground text-xs">
                      {t("validFrom")} {formatDate(assignment.valid_from, locale)}
                      {assignment.valid_to &&
                        ` – ${formatDate(assignment.valid_to, locale)}`}
                    </p>
                  </div>
                  <button
                    onClick={() => handleRemove(assignment.id)}
                    disabled={removeAssignment.isPending}
                    className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
                    aria-label={tc("delete")}
                  >
                    <HugeiconsIcon icon={Delete02Icon} size={15} />
                  </button>
                </div>
              )
            })}
          </div>
        )}
      </div>

      <div>
        <SectionHeading title={t("assignFee")} description="" />
        <div className="space-y-4">
          <div className="space-y-2">
            <Label>{t("feeType")}</Label>
            <Select
              items={feeTypeItems}
              value={feeTypeId || null}
              onValueChange={(v) => setFeeTypeId(v ?? "")}
            >
              <SelectTrigger>
                <SelectValue placeholder={t("selectFeeType")} />
              </SelectTrigger>
              <SelectContent>
                {feeTypeItems.map((item) => (
                  <SelectItem key={item.value} value={item.value}>
                    {item.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>{t("validFrom")}</Label>
            <DatePicker value={validFrom} onChange={setValidFrom} />
          </div>
          <div className="flex justify-end">
            <Button
              size="sm"
              onClick={handleAssign}
              disabled={!feeTypeId || !validFrom || assignFee.isPending}
            >
              {assignFee.isPending ? tc("saving") : t("assignFee")}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
