"use client"

import { useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import { generateDuesAction } from "@/actions/dues"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogBody,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { DownloadIcon, PlayIcon } from "lucide-react"

/**
 * The two things a treasurer does to the whole book at once: assess a year,
 * and hand the open items to the bank.
 */
export function DuesToolbar({
  currentYear,
  /** False while the club has no creditor id or IBAN — the export would fail. */
  sepaReady,
}: {
  currentYear: number
  sepaReady: boolean
}) {
  const t = useTranslations("dues.toolbar")
  const td = useTranslations("dues")
  const router = useRouter()

  const [generateOpen, setGenerateOpen] = useState(false)
  const [sepaOpen, setSepaOpen] = useState(false)
  const [year, setYear] = useState(String(currentYear))
  const [sepaYear, setSepaYear] = useState(String(currentYear))
  const [collectionDate, setCollectionDate] = useState("")
  const [pending, startTransition] = useTransition()

  function generate() {
    startTransition(async () => {
      const result = await generateDuesAction(Number(year))
      if (result.success) {
        setGenerateOpen(false)
        toast.success(t("generatedToast", { count: result.data?.created ?? 0 }))
        router.refresh()
      } else {
        toast.error(td(`errors.${result.error}`))
      }
    })
  }

  const yearValid = /^\d{4}$/.test(year) && Number(year) >= 2000
  const sepaHref =
    `/api/dues/sepa-export?year=${sepaYear}` +
    (collectionDate ? `&collection_date=${collectionDate}` : "")

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Dialog open={generateOpen} onOpenChange={setGenerateOpen}>
        <DialogTrigger
          render={
            <Button variant="outline">
              <PlayIcon />
              {t("generate")}
            </Button>
          }
        />
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("generateTitle")}</DialogTitle>
            <DialogDescription>{t("generateDescription")}</DialogDescription>
          </DialogHeader>
          <DialogBody className="space-y-2">
            <Label htmlFor="generate_year">{t("year")}</Label>
            <Input
              id="generate_year"
              inputMode="numeric"
              value={year}
              onChange={(event) => setYear(event.target.value)}
            />
            <p className="text-xs text-muted-foreground">{t("generateHint")}</p>
          </DialogBody>
          <DialogFooter>
            <DialogClose
              render={
                <Button type="button" variant="outline">
                  {t("cancel")}
                </Button>
              }
            />
            <Button disabled={pending || !yearValid} onClick={generate}>
              {pending ? t("running") : t("generateConfirm")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={sepaOpen} onOpenChange={setSepaOpen}>
        <DialogTrigger
          render={
            <Button variant="outline">
              <DownloadIcon />
              {t("sepa")}
            </Button>
          }
        />
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("sepaTitle")}</DialogTitle>
            <DialogDescription>{t("sepaDescription")}</DialogDescription>
          </DialogHeader>
          <DialogBody className="space-y-4">
            {!sepaReady && (
              <p className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm">
                {t("sepaNotReady")}
              </p>
            )}
            <div className="space-y-2">
              <Label htmlFor="sepa_year">{t("year")}</Label>
              <Input
                id="sepa_year"
                inputMode="numeric"
                value={sepaYear}
                onChange={(event) => setSepaYear(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="collection_date">{t("collectionDate")}</Label>
              <Input
                id="collection_date"
                type="date"
                value={collectionDate}
                onChange={(event) => setCollectionDate(event.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                {t("collectionDateHint")}
              </p>
            </div>
          </DialogBody>
          <DialogFooter>
            <DialogClose
              render={
                <Button type="button" variant="outline">
                  {t("cancel")}
                </Button>
              }
            />
            <Button
              disabled={!sepaReady || !/^\d{4}$/.test(sepaYear)}
              render={
                // Navigation, not fetch: the browser handles the download.
                <a href={sepaHref} download>
                  <DownloadIcon />
                  {t("sepaConfirm")}
                </a>
              }
            />
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
