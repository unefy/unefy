import type { Metadata } from "next"
import { getLocale, getTranslations } from "next-intl/server"

import { Badge } from "@/components/ui/badge"
import { API_BASE } from "@/lib/api"
import { BadgeCheckIcon, ShieldXIcon, XCircleIcon } from "lucide-react"

/**
 * The page a printed certificate's QR code leads to.
 *
 * Public and unauthenticated by design: the reader is an authority's clerk
 * holding a piece of paper, not a member. It shows exactly what the backend's
 * `/verify` endpoint returns and nothing more — whoever finds a lost PDF must
 * not learn on which evenings a person was where.
 *
 * Rendered here rather than by the API so that scanning yields a page. The API
 * still answers JSON at the same path for anything machine-driven.
 */

export const dynamic = "force-dynamic"

type VerifiedCertificate = {
  valid: boolean
  revoked: boolean
  result: string
  period_start: string
  period_end: string
  session_count: number
  issued_at: string
  club_name: string
  member_name: string
}

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("verify")
  return {
    title: t("title"),
    // A verification page has no business in a search index: the codes are
    // credentials, and a crawler following one would publish the answer.
    robots: { index: false, follow: false },
  }
}

async function fetchCertificate(
  code: string
): Promise<VerifiedCertificate | null> {
  try {
    const response = await fetch(
      `${API_BASE}/verify/${encodeURIComponent(code)}`,
      { cache: "no-store" }
    )
    if (!response.ok) return null
    const body = (await response.json()) as { data?: VerifiedCertificate }
    return body.data ?? null
  } catch {
    // An unreachable backend is not a forged certificate. The page says it
    // could not check rather than implying the document is fake.
    return null
  }
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-1">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-sm font-medium tabular-nums">{value}</dd>
    </div>
  )
}

export default async function VerifyPage({
  params,
}: {
  params: Promise<{ code: string }>
}) {
  const [t, locale, { code }] = await Promise.all([
    getTranslations("verify"),
    getLocale(),
    params,
  ])

  const certificate = await fetchCertificate(code)
  const date = (value: string) =>
    new Intl.DateTimeFormat(locale, { dateStyle: "medium" }).format(
      new Date(value)
    )

  return (
    <main className="mx-auto flex min-h-svh max-w-xl flex-col justify-center gap-6 p-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
        <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
      </div>

      {certificate === null ? (
        <div className="space-y-3 rounded-md border border-destructive/40 bg-destructive/5 p-6">
          <div className="flex items-center gap-2 text-destructive">
            <XCircleIcon className="size-5" />
            <span className="font-medium">{t("unknown.title")}</span>
          </div>
          <p className="text-sm text-muted-foreground">
            {t("unknown.description")}
          </p>
          <p className="font-mono text-xs text-muted-foreground">{code}</p>
        </div>
      ) : (
        <div className="space-y-6 rounded-md border p-6">
          {certificate.revoked ? (
            <div className="flex items-center gap-2 text-destructive">
              <ShieldXIcon className="size-5" />
              <span className="font-medium">{t("revoked.title")}</span>
            </div>
          ) : (
            <div className="flex items-center gap-2 text-primary">
              <BadgeCheckIcon className="size-5" />
              <span className="font-medium">{t("valid.title")}</span>
            </div>
          )}

          <dl className="grid gap-4 sm:grid-cols-2">
            <Fact label={t("fields.club")} value={certificate.club_name} />
            <Fact label={t("fields.member")} value={certificate.member_name} />
            <Fact
              label={t("fields.period")}
              value={`${date(certificate.period_start)} – ${date(certificate.period_end)}`}
            />
            <Fact
              label={t("fields.days")}
              value={String(certificate.session_count)}
            />
            <Fact
              label={t("fields.issuedAt")}
              value={date(certificate.issued_at)}
            />
            <div className="space-y-1">
              <dt className="text-xs text-muted-foreground">
                {t("fields.result")}
              </dt>
              <dd>
                <Badge
                  variant={
                    certificate.result === "passed" ? "secondary" : "destructive"
                  }
                >
                  {t(`result.${certificate.result}`)}
                </Badge>
              </dd>
            </div>
          </dl>

          <p className="text-xs text-muted-foreground">
            {certificate.revoked
              ? t("revoked.description")
              : t("valid.description")}
          </p>
        </div>
      )}

      <p className="text-xs text-muted-foreground">
        {t("footer")} <span className="font-mono">{code}</span>
      </p>
    </main>
  )
}
