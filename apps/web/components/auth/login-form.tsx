"use client"

import { useState } from "react"
import { useTranslations } from "next-intl"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { toast } from "sonner"
import { API_URL } from "@/lib/constants"

export function LoginForm() {
  const t = useTranslations("auth")
  const [email, setEmail] = useState("")
  const [sent, setSent] = useState(false)

  function handleGoogleSignIn() {
    window.location.href = `${API_URL}/api/v1/auth/oauth/google`
  }

  async function handleMagicLink(e: React.FormEvent) {
    e.preventDefault()
    try {
      const res = await fetch(`${API_URL}/api/v1/auth/magic-link/request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      })
      if (!res.ok) {
        toast.error(t("error"))
        return
      }
      setSent(true)
    } catch {
      toast.error(t("error"))
    }
  }

  return (
    <div className="space-y-4">
      <Button onClick={handleGoogleSignIn} variant="outline" className="w-full">
        {t("continueWithGoogle")}
      </Button>

      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <span className="w-full border-t" />
        </div>
        <div className="relative flex justify-center text-xs uppercase">
          <span className="bg-background text-muted-foreground px-2">
            {t("or")}
          </span>
        </div>
      </div>

      {!sent ? (
        <form onSubmit={handleMagicLink} className="space-y-3">
          <Input
            type="email"
            placeholder={t("emailAddress")}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <Button type="submit" className="w-full">
            {t("sendMagicLink")}
          </Button>
        </form>
      ) : (
        <p className="text-muted-foreground text-center text-sm">
          {t("checkEmail")}
        </p>
      )}
    </div>
  )
}
