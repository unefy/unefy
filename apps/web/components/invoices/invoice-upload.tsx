"use client"

import { useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { UploadIcon } from "lucide-react"

/**
 * Drop an invoice in and let it say what it is.
 *
 * No form around it. A structured e-invoice fills its own fields, and a scan
 * gets them typed on the record afterwards — asking for a supplier and an
 * amount before the file is anywhere safe is exactly the wrong order.
 *
 * Several files at once, because that is how post arrives: a treasurer opens
 * the folder once a month, not once per invoice. Each is sent on its own so
 * one refusal — a duplicate, most often — does not take the others with it.
 */
export function InvoiceUpload() {
  const t = useTranslations("invoices")
  const router = useRouter()
  const input = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)

  async function send(files: FileList) {
    setBusy(true)
    let filed = 0
    const refused: string[] = []

    for (const file of Array.from(files)) {
      const body = new FormData()
      body.append("file", file)
      try {
        const response = await fetch("/api/incoming-invoices/upload", {
          method: "POST",
          body,
        })
        if (response.ok) {
          filed += 1
          continue
        }
        const payload = await response.json().catch(() => null)
        refused.push(`${file.name}: ${message(t, payload?.error?.code)}`)
      } catch {
        refused.push(`${file.name}: ${t("errors.unreachable")}`)
      }
    }

    setBusy(false)
    if (input.current) input.current.value = ""
    if (filed > 0) {
      toast.success(t("uploaded", { count: filed }))
      router.refresh()
    }
    // One toast per refusal, and the file named: "3 of 5 filed" leaves the
    // treasurer to work out which two, holding the pile in the other hand.
    for (const line of refused) toast.error(line)
  }

  return (
    <>
      <input
        ref={input}
        type="file"
        multiple
        accept=".pdf,.xml,.png,.jpg,.jpeg,.webp"
        className="hidden"
        onChange={(event) => {
          if (event.target.files?.length) void send(event.target.files)
        }}
      />
      <Button
        type="button"
        disabled={busy}
        onClick={() => input.current?.click()}
      >
        <UploadIcon />
        {busy ? t("uploading") : t("upload")}
      </Button>
    </>
  )
}

/** The backend's code, said in words. A duplicate is not a failure to retry. */
function message(t: (key: string) => string, code: string | undefined): string {
  switch (code) {
    case "INVOICE_ALREADY_RECORDED":
      return t("errors.duplicate")
    case "UPLOAD_TOO_LARGE":
      return t("errors.tooLarge")
    case "STORAGE_QUOTA_EXCEEDED":
      return t("errors.quota")
    case "UNSUPPORTED_MEDIA_TYPE":
      return t("errors.unsupported")
    default:
      return t("errors.unknown")
  }
}
