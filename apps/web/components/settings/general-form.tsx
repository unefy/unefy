"use client"

import { useState } from "react"
import { useTranslations } from "next-intl"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { DatePicker } from "@/components/ui/date-picker"
import { Switch } from "@/components/ui/switch"
import { SectionHeading } from "@/components/layout/section-heading"
import { useSettingsForm } from "@/components/settings/settings-shell"
import { toast } from "sonner"
import { API_URL } from "@/lib/constants"

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

      <DangerZoneSection />
    </div>
  )
}

function DangerZoneSection() {
  const t = useTranslations("settings")
  const tc = useTranslations("common")
  const [confirming, setConfirming] = useState(false)
  const [confirmText, setConfirmText] = useState("")
  const [deleting, setDeleting] = useState(false)

  async function handleDelete() {
    setDeleting(true)
    try {
      const res = await fetch(`${API_URL}/api/v1/club`, {
        method: "DELETE",
        credentials: "include",
      })
      if (!res.ok) {
        const data = await res.json()
        toast.error(data.error?.message || tc("error"))
        return
      }
      window.location.href = "/onboarding"
    } catch {
      toast.error(tc("error"))
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div>
      <SectionHeading
        title={t("dangerZone")}
        description={t("dangerZoneDescription")}
      />
      <div className="rounded-3xl border border-destructive/30 bg-destructive/5 p-5">
        <p className="text-sm font-medium text-destructive">
          {t("deleteClub")}
        </p>
        <p className="text-muted-foreground mt-1 text-sm">
          {t("deleteClubDescription")}
        </p>

        {!confirming ? (
          <Button
            variant="outline"
            className="mt-4 border-destructive/30 text-destructive hover:bg-destructive/10"
            onClick={() => setConfirming(true)}
          >
            {t("deleteClub")}
          </Button>
        ) : (
          <div className="mt-4 space-y-3">
            <p className="text-sm">
              {t("deleteClubConfirmPrompt")}
            </p>
            <Input
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              placeholder={t("deleteClubConfirmPlaceholder")}
            />
            <div className="flex gap-2">
              <Button
                variant="outline"
                className="border-destructive/30 bg-destructive text-destructive-foreground hover:bg-destructive/90"
                disabled={confirmText !== t("deleteClubConfirmWord") || deleting}
                onClick={handleDelete}
              >
                {deleting ? tc("loading") : t("deleteClubConfirm")}
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  setConfirming(false)
                  setConfirmText("")
                }}
              >
                {tc("cancel")}
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
