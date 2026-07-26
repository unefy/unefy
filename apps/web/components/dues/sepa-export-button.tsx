"use client"

import { useState } from "react"
import { useTranslations } from "next-intl"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { API_URL } from "@/lib/constants"
import { ApiError } from "@/lib/api-client"
import { useErrorMessage } from "@/lib/errors"

interface SepaExportButtonProps {
  year: number
}

export function SepaExportButton({ year }: SepaExportButtonProps) {
  const t = useTranslations("dues")
  const getErrorMessage = useErrorMessage()
  const [pending, setPending] = useState(false)

  async function handleExport() {
    setPending(true)
    try {
      const res = await fetch(
        `${API_URL}/api/v1/dues/sepa-export?year=${year}`,
        { credentials: "include" },
      )
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new ApiError(
          res.status,
          body.error?.code || "UNKNOWN",
          body.error?.message || "Request failed",
        )
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url
      link.download = `sepa-lastschrift-${year}.xml`
      link.click()
      URL.revokeObjectURL(url)
      const count = res.headers.get("X-Transaction-Count")
      toast.success(t("sepaExportSuccess", { count: Number(count) || 0 }))
    } catch (err) {
      if (err instanceof ApiError && err.code === "VALIDATION_ERROR") {
        toast.error(t("sepaExportNoData"))
      } else {
        toast.error(getErrorMessage(err))
      }
    } finally {
      setPending(false)
    }
  }

  return (
    <Button variant="outline" onClick={handleExport} disabled={pending}>
      {pending ? t("sepaExporting") : t("sepaExport")}
    </Button>
  )
}
