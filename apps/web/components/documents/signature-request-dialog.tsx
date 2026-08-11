"use client"

import { useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import { requestSignatureLinkAction } from "@/actions/documents"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import type { SignatureLink } from "@/lib/types/document"
import { PenLineIcon } from "lucide-react"

/**
 * Hand the signing over to whoever is holding a phone.
 *
 * The link is asked for when this opens, not when the list renders: it is the
 * whole authorisation, so it should exist only while somebody is standing
 * there meaning to sign. Fifteen minutes later it is worth nothing.
 */
export function SignatureRequestDialog({ documentId }: { documentId: string }) {
  const t = useTranslations("documents.signing")
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [link, setLink] = useState<SignatureLink | null>(null)
  const [pending, startTransition] = useTransition()

  function onOpenChange(next: boolean) {
    setOpen(next)
    if (!next) {
      setLink(null)
      // Somebody may have signed while this was open; the list says whether.
      router.refresh()
      return
    }
    startTransition(async () => {
      const result = await requestSignatureLinkAction(documentId)
      if (result.success && result.data) {
        setLink(result.data)
        return
      }
      toast.error(t("failed"))
      setOpen(false)
    })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger
        render={
          <Button
            variant="ghost"
            size="sm"
            aria-label={t("action")}
            title={t("action")}
          >
            <PenLineIcon className="size-4" />
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("title")}</DialogTitle>
          <DialogDescription>{t("description")}</DialogDescription>
        </DialogHeader>
        <DialogBody className="space-y-4">
          {link === null ? (
            <p className="text-sm text-muted-foreground">{t("loading")}</p>
          ) : (
            <>
              <div className="flex justify-center">
                <QrCode rows={link.qr} />
              </div>
              <div className="space-y-1.5">
                <p className="rounded-md border bg-muted/40 p-2 font-mono text-xs break-all">
                  {link.url}
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full"
                  onClick={() => {
                    void navigator.clipboard.writeText(link.url)
                    toast.success(t("copied"))
                  }}
                >
                  {t("copy")}
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                {t("expires", { minutes: Math.round(link.expires_in / 60) })}
              </p>
            </>
          )}
        </DialogBody>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={pending}
          >
            {t("close")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/**
 * The QR, drawn from the module matrix the backend computed.
 *
 * Squares in an SVG rather than an image: the encoder already exists on the
 * server, this needs no dependency, and nothing server-made is injected into
 * the page as markup.
 */
function QrCode({ rows }: { rows: string[] }) {
  const size = rows.length
  const quiet = 2
  const side = size + quiet * 2
  return (
    <svg
      viewBox={`0 0 ${side} ${side}`}
      className="size-48 rounded-md bg-white p-1"
      role="img"
      aria-hidden="true"
    >
      {rows.map((row, y) =>
        [...row].map((module, x) =>
          module === "1" ? (
            <rect
              key={`${x}-${y}`}
              x={x + quiet}
              y={y + quiet}
              width={1}
              height={1}
              fill="#000000"
            />
          ) : null
        )
      )}
    </svg>
  )
}
