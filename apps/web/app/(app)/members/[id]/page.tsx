"use client"

import { useTranslations } from "next-intl"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { DatePicker } from "@/components/ui/date-picker"
import { SectionHeading } from "@/components/layout/section-heading"
import { useMemberDetail } from "@/components/members/member-detail-shell"

export default function MemberPersonalPage() {
  const t = useTranslations("members")
  const { form, handleChange } = useMemberDetail()

  return (
    <div className="space-y-10">
      {/* Personal */}
      <div>
        <SectionHeading title={t("personalInfo")} description="" />
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>{t("firstName")}</Label>
              <Input
                value={form.first_name || ""}
                onChange={(e) => handleChange("first_name", e.target.value)}
                placeholder={t("firstNamePlaceholder")}
              />
            </div>
            <div className="space-y-2">
              <Label>{t("lastName")}</Label>
              <Input
                value={form.last_name || ""}
                onChange={(e) => handleChange("last_name", e.target.value)}
                placeholder={t("lastNamePlaceholder")}
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>{t("birthday")}</Label>
              <DatePicker
                value={form.birthday || ""}
                onChange={(v) => handleChange("birthday", v)}
              />
            </div>
            <div className="space-y-2">
              <Label>{t("email")}</Label>
              <Input
                type="email"
                value={form.email || ""}
                onChange={(e) => handleChange("email", e.target.value)}
                placeholder={t("emailPlaceholder")}
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>{t("phone")}</Label>
              <Input
                type="tel"
                value={form.phone || ""}
                onChange={(e) => handleChange("phone", e.target.value)}
                placeholder={t("phonePlaceholder")}
              />
            </div>
            <div className="space-y-2">
              <Label>{t("mobile")}</Label>
              <Input
                type="tel"
                value={form.mobile || ""}
                onChange={(e) => handleChange("mobile", e.target.value)}
                placeholder={t("mobilePlaceholder")}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Address */}
      <div>
        <SectionHeading title={t("address")} description="" />
        <div className="space-y-4">
          <div className="space-y-2">
            <Label>{t("street")}</Label>
            <Input
              value={form.street || ""}
              onChange={(e) => handleChange("street", e.target.value)}
              placeholder={t("streetPlaceholder")}
            />
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label>{t("zip")}</Label>
              <Input
                value={form.zip_code || ""}
                onChange={(e) => handleChange("zip_code", e.target.value)}
                placeholder={t("zipPlaceholder")}
              />
            </div>
            <div className="col-span-2 space-y-2">
              <Label>{t("city")}</Label>
              <Input
                value={form.city || ""}
                onChange={(e) => handleChange("city", e.target.value)}
                placeholder={t("cityPlaceholder")}
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>{t("state")}</Label>
              <Input
                value={form.state || ""}
                onChange={(e) => handleChange("state", e.target.value)}
                placeholder={t("statePlaceholder")}
              />
            </div>
            <div className="space-y-2">
              <Label>{t("country")}</Label>
              <Input
                value={form.country || ""}
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
