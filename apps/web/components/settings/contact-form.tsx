"use client"

import { useTranslations } from "next-intl"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { SectionHeading } from "@/components/layout/section-heading"
import { useSettingsForm } from "@/components/settings/settings-shell"

export function ContactForm() {
  const t = useTranslations("settings")
  const { form, handleChange } = useSettingsForm()

  return (
    <div className="space-y-10">
      <div>
        <SectionHeading
          title={t("contact")}
          description={t("contactDescription")}
        />
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="email">{t("email")}</Label>
              <Input
                id="email"
                type="email"
                value={form.email as string}
                onChange={(e) => handleChange("email", e.target.value)}
                placeholder={t("emailPlaceholder")}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="phone">{t("phone")}</Label>
              <Input
                id="phone"
                type="tel"
                value={form.phone as string}
                onChange={(e) => handleChange("phone", e.target.value)}
                placeholder={t("phonePlaceholder")}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="website">{t("website")}</Label>
            <Input
              id="website"
              type="url"
              value={form.website as string}
              onChange={(e) => handleChange("website", e.target.value)}
              placeholder={t("websitePlaceholder")}
            />
          </div>
        </div>
      </div>

      <div>
        <SectionHeading
          title={t("address")}
          description={t("addressDescription")}
        />
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="street">{t("street")}</Label>
            <Input
              id="street"
              value={form.street as string}
              onChange={(e) => handleChange("street", e.target.value)}
              placeholder={t("streetPlaceholder")}
            />
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label htmlFor="zip_code">{t("zip")}</Label>
              <Input
                id="zip_code"
                value={form.zip_code as string}
                onChange={(e) => handleChange("zip_code", e.target.value)}
                placeholder={t("zipPlaceholder")}
              />
            </div>
            <div className="col-span-2 space-y-2">
              <Label htmlFor="city">{t("city")}</Label>
              <Input
                id="city"
                value={form.city as string}
                onChange={(e) => handleChange("city", e.target.value)}
                placeholder={t("cityPlaceholder")}
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="state">{t("state")}</Label>
              <Input
                id="state"
                value={form.state as string}
                onChange={(e) => handleChange("state", e.target.value)}
                placeholder={t("statePlaceholder")}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="country">{t("country")}</Label>
              <Input
                id="country"
                value={form.country as string}
                onChange={(e) => handleChange("country", e.target.value)}
                placeholder={t("countryPlaceholder")}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
