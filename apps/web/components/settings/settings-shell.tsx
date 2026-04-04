"use client"

import { createContext, useContext, useState } from "react"
import { useTranslations } from "next-intl"
import { Button } from "@/components/ui/button"
import { PageHeader } from "@/components/layout/page-header"
import { SubNavLayout } from "@/components/layout/sub-nav-layout"
import { useUpdateClub } from "@/hooks/use-club"
import { toast } from "sonner"
import type { Club } from "@/lib/types/club"

interface SettingsContextValue {
  form: Record<string, any>
  handleChange: (name: string, value: string | boolean) => void
}

const SettingsContext = createContext<SettingsContextValue | null>(null)

export function useSettingsForm() {
  const ctx = useContext(SettingsContext)
  if (!ctx) throw new Error("useSettingsForm must be used within SettingsShell")
  return ctx
}

interface SettingsShellProps {
  club: Club
  children: React.ReactNode
}

export function SettingsShell({ club, children }: SettingsShellProps) {
  const t = useTranslations("settings")
  const tc = useTranslations("common")
  const updateClub = useUpdateClub()

  const [form, setForm] = useState({
    name: club.name || "",
    short_name: club.short_name || "",
    email: club.email || "",
    phone: club.phone || "",
    website: club.website || "",
    street: club.street || "",
    zip_code: club.zip_code || "",
    city: club.city || "",
    state: club.state || "",
    country: club.country || "Deutschland",
    description: club.description || "",
    founded_at: club.founded_at || "",
    registration_number: club.registration_number || "",
    registration_court: club.registration_court || "",
    tax_number: club.tax_number || "",
    tax_office: club.tax_office || "",
    is_nonprofit: club.is_nonprofit || false,
    nonprofit_since: club.nonprofit_since || "",
    member_number_format: club.member_number_format || "{NUM:3}",
    member_number_next: String(club.member_number_next || 1),
  })

  function handleChange(name: string, value: string | boolean) {
    setForm((prev) => ({ ...prev, [name]: value }))
  }

  function handleSubmit() {
    updateClub.mutate(form, {
      onSuccess: () => toast.success(tc("saved")),
      onError: (err) => toast.error(err.message),
    })
  }

  const navItems = [
    { label: t("general"), href: "/settings" },
    { label: t("contactAndAddress"), href: "/settings/contact" },
    { label: t("defaults"), href: "/settings/defaults" },
  ]

  return (
    <SettingsContext.Provider value={{ form, handleChange }}>
      <div className="space-y-8">
        <PageHeader title={t("title")} description={t("description")}>
          <Button onClick={handleSubmit} disabled={updateClub.isPending}>
            {updateClub.isPending ? tc("saving") : tc("save")}
          </Button>
        </PageHeader>

        <SubNavLayout items={navItems}>{children}</SubNavLayout>
      </div>
    </SettingsContext.Provider>
  )
}
