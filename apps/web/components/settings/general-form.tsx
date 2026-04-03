"use client"

import { useTranslations } from "next-intl"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { DatePicker } from "@/components/ui/date-picker"
import { Switch } from "@/components/ui/switch"
import { SectionHeading } from "@/components/layout/section-heading"
import { useSettingsForm } from "@/components/settings/settings-shell"

export function GeneralForm() {
  const t = useTranslations("settings")
  const { form, handleChange } = useSettingsForm()

  return (
    <div className="space-y-10">
      <div>
        <SectionHeading
          title={t("general")}
          description={t("generalDescription")}
        />
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="name">{t("clubName")}</Label>
              <Input
                id="name"
                value={form.name as string}
                onChange={(e) => handleChange("name", e.target.value)}
                placeholder={t("clubNamePlaceholder")}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="short_name">{t("shortName")}</Label>
              <Input
                id="short_name"
                value={form.short_name as string}
                onChange={(e) => handleChange("short_name", e.target.value)}
                placeholder={t("shortNamePlaceholder")}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="description">{t("description")}</Label>
            <Textarea
              id="description"
              value={form.description as string}
              onChange={(e) => handleChange("description", e.target.value)}
              placeholder={t("descriptionPlaceholder")}
            />
          </div>
        </div>
      </div>

      <div>
        <SectionHeading
          title={t("legal")}
          description={t("legalDescription")}
        />
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>{t("founded")}</Label>
              <DatePicker
                value={form.founded_at as string}
                onChange={(v) => handleChange("founded_at", v)}
                placeholder={t("foundedPlaceholder")}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="registration_number">
                {t("registrationNumber")}
              </Label>
              <Input
                id="registration_number"
                value={form.registration_number as string}
                onChange={(e) =>
                  handleChange("registration_number", e.target.value)
                }
                placeholder={t("registrationNumberPlaceholder")}
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="registration_court">
                {t("registrationCourt")}
              </Label>
              <Input
                id="registration_court"
                value={form.registration_court as string}
                onChange={(e) =>
                  handleChange("registration_court", e.target.value)
                }
                placeholder={t("registrationCourtPlaceholder")}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="tax_number">{t("taxNumber")}</Label>
              <Input
                id="tax_number"
                value={form.tax_number as string}
                onChange={(e) => handleChange("tax_number", e.target.value)}
                placeholder={t("taxNumberPlaceholder")}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="tax_office">{t("taxOffice")}</Label>
            <Input
              id="tax_office"
              value={form.tax_office as string}
              onChange={(e) => handleChange("tax_office", e.target.value)}
              placeholder={t("taxOfficePlaceholder")}
            />
          </div>
          <div className="flex items-center justify-between rounded-3xl bg-input/50 px-4 py-3">
            <div>
              <p className="text-sm font-medium">{t("nonprofitStatus")}</p>
              <p className="text-muted-foreground text-xs">
                {t("nonprofitDescription")}
              </p>
            </div>
            <Switch
              checked={form.is_nonprofit as boolean}
              onCheckedChange={(checked) =>
                handleChange("is_nonprofit", !!checked)
              }
            />
          </div>
          {form.is_nonprofit && (
            <div className="space-y-2">
              <Label>{t("nonprofitSince")}</Label>
              <DatePicker
                value={form.nonprofit_since as string}
                onChange={(v) => handleChange("nonprofit_since", v)}
                placeholder={t("nonprofitSincePlaceholder")}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
