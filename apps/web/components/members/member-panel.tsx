"use client"
import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { DatePicker } from "@/components/ui/date-picker"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { SectionHeading } from "@/components/layout/section-heading"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useMember, useUpdateMember } from "@/hooks/use-members"
import { useErrorMessage } from "@/lib/errors"
import { useClub } from "@/hooks/use-club"
import { getStatusLabel, parseMemberStatuses } from "@/lib/types/club"
import { toast } from "sonner"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  Cancel01Icon,
  ArrowRight01Icon,
  UserIcon,
  UserMultiple02Icon,
} from "@hugeicons/core-free-icons"
interface MemberPanelProps {
  memberId: string
  onClose: () => void
}
export function MemberPanel({ memberId, onClose }: MemberPanelProps) {
  const t = useTranslations("members")
  const tc = useTranslations("common")
  const router = useRouter()
  const { data: member, isLoading } = useMember(memberId)
  const updateMember = useUpdateMember()
  const getErrorMessage = useErrorMessage()
  const [form, setForm] = useState<Record<string, string | null>>({})
  const [dirty, setDirty] = useState(false)
  useEffect(() => {
    if (member) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setForm({
        first_name: member.first_name,
        last_name: member.last_name,
        email: member.email,
        phone: member.phone,
        mobile: member.mobile,
        birthday: member.birthday,
        street: member.street,
        zip_code: member.zip_code,
        city: member.city,
        state: member.state,
        country: member.country,
        joined_at: member.joined_at,
        left_at: member.left_at,
        status: member.status,
        category: member.category,
        notes: member.notes,
        member_number: member.member_number,
      })
      setDirty(false)
    }
  }, [member])
  function handleChange(name: string, value: string | null) {
    setForm((prev) => ({ ...prev, [name]: value === "" ? null : value }))
    setDirty(true)
  }
  function handleSave() {
    updateMember.mutate(
      { id: memberId, data: form },
      {
        onSuccess: () => {
          toast.success(tc("saved"))
          setDirty(false)
        },
        onError: (err) => toast.error(getErrorMessage(err)),
      },
    )
  }
  const { data: club } = useClub()
  const memberStatuses = parseMemberStatuses(club?.member_statuses ?? null)
  const statusItems = memberStatuses.map((s) => ({
    value: s.key,
    label: getStatusLabel(s, t),
  }))

  if (isLoading || !member) {
    return (
      <div className="fixed right-0 top-0 z-30 flex h-screen w-[400px] flex-col bg-card">
        <div className="p-4 space-y-4">
          <div className="h-8 w-48 animate-pulse rounded bg-muted" />
          <div className="h-4 w-24 animate-pulse rounded bg-muted" />
        </div>
      </div>
    )
  }
  return (
    <div className="fixed right-0 top-0 z-30 flex h-screen w-[400px] flex-col bg-card">
      {/* Header — pt-8 matches main content py-8 */}
      <div className="flex items-start justify-between px-4 pt-8 pb-2 shrink-0">
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-2xl font-bold tracking-tight">
            {member.first_name} {member.last_name}
          </h2>
          <Input
            value={form.member_number || ""}
            onChange={(e) => handleChange("member_number", e.target.value)}
            placeholder={t("memberNumberPlaceholder")}
            className="mt-1 h-7 w-24 text-xs px-2 bg-transparent"
          />
        </div>
        <div className="flex items-center gap-1 pt-1">
          <button
            onClick={() => router.push(`/members/${memberId}`)}
            className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            <HugeiconsIcon icon={ArrowRight01Icon} size={16} />
          </button>
          <button
            onClick={onClose}
            className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            <HugeiconsIcon icon={Cancel01Icon} size={16} />
          </button>
        </div>
      </div>
      {/* Tabs + scrollable content */}
      <Tabs defaultValue="personal" className="flex-1 flex flex-col min-h-0">
        <div className="px-4 shrink-0">
          <TabsList>
            <TabsTrigger value="personal">
              <HugeiconsIcon icon={UserIcon} size={14} />
            </TabsTrigger>
            <TabsTrigger value="membership">
              <HugeiconsIcon icon={UserMultiple02Icon} size={14} />
            </TabsTrigger>
          </TabsList>
        </div>
        <div className="flex-1 overflow-y-auto">
          <TabsContent value="personal" className="px-4 py-4">
            <div className="space-y-8">
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
                  <div className="space-y-2">
                    <Label>{t("birthday")}</Label>
                    <DatePicker
                      value={form.birthday || ""}
                      onChange={(v) => handleChange("birthday", v)}
                    />
                  </div>
                </div>
              </div>
              <div>
                <SectionHeading title={t("contactInfo")} description="" />
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label>{t("email")}</Label>
                    <Input
                      type="email"
                      value={form.email || ""}
                      onChange={(e) => handleChange("email", e.target.value)}
                      placeholder={t("emailPlaceholder")}
                    />
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
                </div>
              </div>
            </div>
          </TabsContent>
          <TabsContent value="membership" className="px-4 py-4">
            <div className="space-y-8">
              <div>
                <SectionHeading title={t("membershipInfo")} description="" />
                <div className="space-y-4">
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
                      className="text-sm min-h-20"
                    />
                  </div>
                </div>
              </div>
            </div>
          </TabsContent>
          <div className="flex justify-end px-4 pt-6 pb-4">
            <Button
              size="sm"
              onClick={handleSave}
              disabled={updateMember.isPending || !dirty}
            >
              {updateMember.isPending ? tc("saving") : tc("save")}
            </Button>
          </div>
        </div>
      </Tabs>
    </div>
  )
}
