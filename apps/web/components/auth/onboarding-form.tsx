"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { toast } from "sonner"
import { API_URL } from "@/lib/constants"

interface OnboardingFormProps {
  userName: string
}

export function OnboardingForm({ userName }: OnboardingFormProps) {
  const t = useTranslations("auth")
  const [clubName, setClubName] = useState("")
  const [loading, setLoading] = useState(false)
  const router = useRouter()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)

    try {
      const res = await fetch(
        `${API_URL}/api/v1/auth/onboarding/create-club`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ club_name: clubName }),
        },
      )

      if (!res.ok) {
        const data = await res.json()
        toast.error(data.error?.message || t("error"))
        return
      }

      router.push("/")
      router.refresh()
    } catch {
      toast.error(t("error"))
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="club-name">{t("clubName")}</Label>
        <Input
          id="club-name"
          placeholder={t("clubNamePlaceholder")}
          value={clubName}
          onChange={(e) => setClubName(e.target.value)}
          required
          minLength={2}
          maxLength={255}
        />
      </div>

      <Button type="submit" className="w-full" disabled={loading}>
        {loading ? t("creating") : t("createClubButton")}
      </Button>
    </form>
  )
}
