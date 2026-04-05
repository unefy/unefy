"use client"

import { useTranslations } from "next-intl"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { DatePicker } from "@/components/ui/date-picker"
import { SectionHeading } from "@/components/layout/section-heading"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useMemberDetail } from "@/components/members/member-detail-shell"
import { useClub } from "@/hooks/use-club"
import { getStatusLabel, parseMemberStatuses } from "@/lib/types/club"

export default function MemberMembershipPage() {
  const t = useTranslations("members")
  const { form, handleChange } = useMemberDetail()
  const { data: club } = useClub()
  const memberStatuses = parseMemberStatuses(club?.member_statuses ?? null)
  const statusItems = memberStatuses.map((s) => ({
    value: s.key,
    label: getStatusLabel(s, t),
  }))

  return (
    <div className="space-y-4">
      <SectionHeading title={t("membershipInfo")} description="" />
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>{t("status")}</Label>
          <Select
            items={statusItems}
            value={form.status || "active"}
            onValueChange={(v) => handleChange("status", v)}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {statusItems.map((item) => (
                <SelectItem key={item.value} value={item.value}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label>{t("category")}</Label>
          <Input
            value={form.category || ""}
            onChange={(e) => handleChange("category", e.target.value)}
            placeholder={t("categoryPlaceholder")}
          />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>{t("joinedAt")}</Label>
          <DatePicker
            value={form.joined_at || ""}
            onChange={(v) => handleChange("joined_at", v)}
          />
        </div>
        <div className="space-y-2">
          <Label>{t("leftAt")}</Label>
          <DatePicker
            value={form.left_at || ""}
            onChange={(v) => handleChange("left_at", v)}
          />
        </div>
      </div>
      <div className="space-y-2">
        <Label>{t("notes")}</Label>
        <Textarea
          value={form.notes || ""}
          onChange={(e) => handleChange("notes", e.target.value)}
          placeholder={t("notesPlaceholder")}
        />
      </div>
    </div>
  )
}
