import { getLocale, getTranslations } from "next-intl/server"

import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { formatDateTime } from "@/lib/time"
import type { ProofChainStatus } from "@/lib/types/shooting"

/**
 * The proof chain at a glance — length, intact yes/no, last external anchor.
 *
 * Server component: the status is fetched by the page and purely displayed;
 * nothing here needs interaction.
 */
export async function ChainStatusCard({
  status,
  timeZone,
}: {
  status: ProofChainStatus
  timeZone: string
}) {
  const [t, locale] = await Promise.all([
    getTranslations("shooting.chain"),
    getLocale(),
  ])

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          {t("title")}
          {status.length === 0 ? (
            <Badge variant="outline">{t("emptyBadge")}</Badge>
          ) : status.valid ? (
            <Badge>{t("validBadge")}</Badge>
          ) : (
            <Badge variant="destructive">{t("brokenBadge")}</Badge>
          )}
        </CardTitle>
        <CardDescription>{t("hint")}</CardDescription>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
          <dt className="text-muted-foreground">{t("length")}</dt>
          <dd className="tabular-nums">{status.length}</dd>
          {status.broken_at_seq !== null && (
            <>
              <dt className="text-muted-foreground">{t("brokenAt")}</dt>
              <dd className="tabular-nums text-destructive">
                {status.broken_at_seq}
              </dd>
            </>
          )}
          <dt className="text-muted-foreground">{t("anchor")}</dt>
          <dd>
            {status.anchored_at
              ? t("anchoredAt", {
                  seq: status.anchored_to_seq ?? 0,
                  at: formatDateTime(status.anchored_at, locale, timeZone),
                })
              : t("noAnchor")}
          </dd>
        </dl>
      </CardContent>
    </Card>
  )
}
