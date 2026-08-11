"use client"

import { useState, useTransition } from "react"
import { useTranslations } from "next-intl"

import { submitSignatureAction } from "@/actions/documents"
import { SignaturePad } from "@/components/documents/signature-pad"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { CheckCircle2Icon } from "lucide-react"

/**
 * Draw, then send. No name to type and nothing to confirm twice: the person
 * holding the phone was handed the link by somebody who meant them to sign
 * this one document, and asking them to fill in a form would only invite
 * typing somebody else's name.
 */
export function SignForm({ token }: { token: string }) {
  const t = useTranslations("sign")
  const [signature, setSignature] = useState<string | null>(null)
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

  function submit() {
    if (!signature) return
    startTransition(async () => {
      const result = await submitSignatureAction(token, signature)
      if (result.success) {
        setDone(true)
        return
      }
      setError(result.error === "notFound" ? t("expiredHint") : t("failed"))
    })
  }

  return (
    <div className="space-y-4">
      <SignaturePad onChange={setSignature} disabled={pending} />
      {error === null ? null : (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      <Button
        className="w-full"
        onClick={submit}
        disabled={pending || signature === null}
      >
        {pending ? t("submitting") : t("submit")}
      </Button>
    </div>
  )
}
