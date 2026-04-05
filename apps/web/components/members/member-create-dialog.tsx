"use client"

import { useState } from "react"
import { useTranslations } from "next-intl"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { DatePicker } from "@/components/ui/date-picker"
import { useCreateMember } from "@/hooks/use-members"
import { toast } from "sonner"
import { useErrorMessage } from "@/lib/errors"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  UserIcon,
  Location01Icon,
  UserMultiple02Icon,
} from "@hugeicons/core-free-icons"
import type { MemberCreate } from "@/lib/types/member"

const EMPTY_FORM: MemberCreate = {
  first_name: "",
  last_name: "",
  email: null,
  phone: null,
  mobile: null,
  birthday: null,
  street: null,
  zip_code: null,
  city: null,
  state: null,
  country: "Deutschland",
  joined_at: null,
  status: "active",
  category: null,
  notes: null,
}

const STEPS = ["personal", "contact", "membership"] as const
type Step = (typeof STEPS)[number]

export function MemberCreateDialog() {
  const t = useTranslations("members")
  const tc = useTranslations("common")
  const [open, setOpen] = useState(false)
  const [step, setStep] = useState<Step>("personal")
  const createMember = useCreateMember()
  const getErrorMessage = useErrorMessage()
  const [form, setForm] = useState<MemberCreate>({ ...EMPTY_FORM })

  const stepIndex = STEPS.indexOf(step)
  const isFirst = stepIndex === 0
  const isLast = stepIndex === STEPS.length - 1

  function handleChange(name: string, value: string | null) {
    setForm((prev) => ({ ...prev, [name]: value === "" ? null : value }))
  }

  function handleNext() {
    if (!isLast) setStep(STEPS[stepIndex + 1])
  }

  function handleBack() {
    if (!isFirst) setStep(STEPS[stepIndex - 1])
  }

  function handleSubmit() {
    createMember.mutate(form, {
      onSuccess: () => {
        toast.success(tc("saved"))
        handleClose()
      },
      onError: (err) => toast.error(getErrorMessage(err)),
    })
  }

  function handleClose() {
    setOpen(false)
    setForm({ ...EMPTY_FORM })
    setStep("personal")
  }

  const canProceed =
    (form.first_name ?? "").trim() !== "" &&
    (form.last_name ?? "").trim() !== ""

  return (
    <>
      <Button onClick={() => setOpen(true)}>{t("addMember")}</Button>
      <Dialog open={open} onOpenChange={(v) => !v && handleClose()}>
        <DialogContent className="sm:max-w-4xl">
          <DialogHeader>
            <DialogTitle>{t("createMember")}</DialogTitle>
            <DialogDescription>{t("description")}</DialogDescription>
          </DialogHeader>

          <Tabs value={step} onValueChange={(v) => setStep(v as Step)}>
            <TabsList>
              <TabsTrigger value="personal">
                <HugeiconsIcon icon={UserIcon} size={14} />
                {t("personalInfo")}
              </TabsTrigger>
              <TabsTrigger value="contact">
                <HugeiconsIcon icon={Location01Icon} size={14} />
                {t("address")}
              </TabsTrigger>
              <TabsTrigger value="membership">
                <HugeiconsIcon icon={UserMultiple02Icon} size={14} />
                {t("membershipInfo")}
              </TabsTrigger>
            </TabsList>

            <TabsContent value="personal" className="min-h-[16rem] pt-6">
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>{t("firstName")} *</Label>
                    <Input
                      value={form.first_name ?? ""}
                      onChange={(e) =>
                        handleChange("first_name", e.target.value)
                      }
                      placeholder={t("firstNamePlaceholder")}
                      autoFocus
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>{t("lastName")} *</Label>
                    <Input
                      value={form.last_name ?? ""}
                      onChange={(e) =>
                        handleChange("last_name", e.target.value)
                      }
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
            </TabsContent>

            <TabsContent value="contact" className="min-h-[16rem] pt-6">
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
                      onChange={(e) =>
                        handleChange("zip_code", e.target.value)
                      }
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
                      value={form.country || "Deutschland"}
                      onChange={(e) => handleChange("country", e.target.value)}
                      placeholder={t("countryPlaceholder")}
                    />
                  </div>
                </div>
              </div>
            </TabsContent>

            <TabsContent value="membership" className="min-h-[16rem] pt-6">
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>{t("joinedAt")}</Label>
                    <DatePicker
                      value={form.joined_at || ""}
                      onChange={(v) => handleChange("joined_at", v)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>{t("category")}</Label>
                    <Input
                      value={form.category || ""}
                      onChange={(e) =>
                        handleChange("category", e.target.value)
                      }
                      placeholder={t("categoryPlaceholder")}
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
            </TabsContent>
          </Tabs>

          <DialogFooter>
            <div className="flex w-full items-center justify-between">
              <div>
                {!isFirst && (
                  <Button variant="outline" onClick={handleBack}>
                    ← {tc("back")}
                  </Button>
                )}
              </div>
              {/* Reversed DOM order so Tab reaches primary action first. */}
              <div className="flex flex-row-reverse gap-2">
                {isLast ? (
                  <Button
                    onClick={handleSubmit}
                    disabled={!canProceed || createMember.isPending}
                  >
                    {createMember.isPending
                      ? tc("saving")
                      : t("createMember")}
                  </Button>
                ) : (
                  <Button onClick={handleNext} disabled={!canProceed}>
                    {tc("next")} →
                  </Button>
                )}
                <Button variant="outline" onClick={handleClose}>
                  {tc("cancel")}
                </Button>
              </div>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
