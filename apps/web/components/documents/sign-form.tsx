"use client"

import { useState, useTransition } from "react"
import { useTranslations } from "next-intl"

import { submitSignatureAction } from "@/actions/documents"
import { SignatureSheet } from "@/components/documents/signature-sheet"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { CheckCircle2Icon, PenLineIcon } from "lucide-react"

/**
 * Read, then draw, then send. No name to type and nothing to confirm twice:
 * the person holding the phone was handed the link by somebody who meant them
 * to sign this one document, and asking them to fill in a form would only
 * invite typing somebody else's name.
 *
 * The pad is not on the page but over it. A signature wants the whole screen,
 * and the document above it wants reading first — one button separates the
 * two, and it is also the tap that turns the phone sideways.
 */
export function SignForm({ token }: { token: string }) {
  const t = useTranslations("sign")
  const [open, setOpen] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pending, startTransition] = useTransition()

  if (done) {
    return (
      <Alert>
        <CheckCircle2Icon />
        <AlertDescription>{t("thanks")}</AlertDescription>
      </Alert>
    )
  }

  function submit(signature: string) {
    startTransition(async () => {
      const result = await submitSignatureAction(token, signature)
      setOpen(false)
      if (result.success) {
        setDone(true)
        return
      }
      setError(result.error === "notFound" ? t("expiredHint") : t("failed"))
    })
  }

  return (
    <div className="space-y-4">
      {error === null ? null : (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      <Button
        className="w-full"
        size="lg"
        onClick={() => setOpen(true)}
        disabled={pending}
      >
        <PenLineIcon />
        {t("open")}
      </Button>
      {open ? (
        <SignatureSheet
          confirmLabel={t("submit")}
          pending={pending}
          onConfirm={submit}
          onCancel={() => setOpen(false)}
        />
      ) : null}
    </div>
  )
}
