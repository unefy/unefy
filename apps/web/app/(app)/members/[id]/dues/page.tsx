"use client"

import { useTranslations } from "next-intl"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { DatePicker } from "@/components/ui/date-picker"
import { SectionHeading } from "@/components/layout/section-heading"
import { useMemberDetail } from "@/components/members/member-detail-shell"
import { MemberFeesSection } from "@/components/dues/member-fees-section"

export default function MemberDuesPage() {
  const t = useTranslations("members")
  const { form, handleChange, member } = useMemberDetail()

  return (
    <div className="space-y-10">
      <div>
        <SectionHeading title={t("bankData")} description="" />
        <div className="space-y-4">
          <div className="space-y-2">
            <Label>{t("accountHolder")}</Label>
            <Input
              value={form.account_holder || ""}
              onChange={(e) => handleChange("account_holder", e.target.value)}
              placeholder={`${member.first_name} ${member.last_name}`}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>{t("iban")}</Label>
              <Input
                value={form.iban || ""}
                onChange={(e) => handleChange("iban", e.target.value)}
                placeholder="DE00 0000 0000 0000 0000 00"
              />
            </div>
            <div className="space-y-2">
              <Label>{t("bic")}</Label>
              <Input
                value={form.bic || ""}
                onChange={(e) => handleChange("bic", e.target.value)}
                placeholder="XXXXDEXX"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>{t("mandateReference")}</Label>
              <Input
                value={form.sepa_mandate_reference || ""}
                onChange={(e) =>
                  handleChange("sepa_mandate_reference", e.target.value)
                }
                placeholder={t("mandateReferencePlaceholder")}
              />
            </div>
            <div className="space-y-2">
              <Label>{t("mandateDate")}</Label>
              <DatePicker
                value={form.sepa_mandate_date || ""}
                onChange={(v) => handleChange("sepa_mandate_date", v)}
              />
            </div>
          </div>
        </div>
      </div>

      <MemberFeesSection memberId={member.id} />
    </div>
  )
}
