"use client"

import { useTranslations } from "next-intl"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { SectionHeading } from "@/components/layout/section-heading"
import { useSettingsForm } from "@/components/settings/settings-shell"

export function PaymentForm() {
  const t = useTranslations("settings")
  const { form, handleChange } = useSettingsForm()

  return (
    <div className="space-y-10">
      <div>
        <SectionHeading
          title={t("sepa")}
          description={t("sepaDescription")}
        />
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="sepa_creditor_id">{t("sepaCreditorId")}</Label>
            <Input
              id="sepa_creditor_id"
              value={form.sepa_creditor_id as string}
              onChange={(e) => handleChange("sepa_creditor_id", e.target.value)}
              placeholder={t("sepaCreditorIdPlaceholder")}
            />
            <p className="text-muted-foreground text-xs">
              {t("sepaCreditorIdHelp")}
            </p>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div className="col-span-2 space-y-2">
              <Label htmlFor="iban">{t("iban")}</Label>
              <Input
                id="iban"
                value={form.iban as string}
                onChange={(e) => handleChange("iban", e.target.value)}
                placeholder={t("ibanPlaceholder")}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="bic">{t("bic")}</Label>
              <Input
                id="bic"
                value={form.bic as string}
                onChange={(e) => handleChange("bic", e.target.value)}
                placeholder={t("bicPlaceholder")}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
