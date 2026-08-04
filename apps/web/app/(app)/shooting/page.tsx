import { notFound } from "next/navigation"
import { getTranslations } from "next-intl/server"

import { CertificatesTable } from "@/components/shooting/certificates-table"
import { ChainStatusCard } from "@/components/shooting/chain-status-card"
import { ProofCheck } from "@/components/shooting/proof-check"
import { RangeBookExport } from "@/components/shooting/range-book-export"
import { getClubTimeZone } from "@/lib/attendance"
import { getClub } from "@/lib/club"
import {
  getProofChainStatus,
  listShootingCertificates,
  listShootingRules,
} from "@/lib/shooting"

export default async function ShootingPage() {
  // Two gates, both mapped to "this page does not exist": a club without the
  // module, and a member role the backend refuses. The backend is the real
  // boundary — this only keeps the UI honest about it.
  const club = await getClub().catch(() => null)
  if (!club?.modules.includes("shooting")) notFound()

  const [t, rules, certificates, chain, timeZone] = await Promise.all([
    getTranslations("shooting"),
    listShootingRules().catch(() => null),
    listShootingCertificates().catch(() => null),
    getProofChainStatus().catch(() => null),
    getClubTimeZone(),
  ])
  if (rules === null || certificates === null) notFound()

  return (
    <>
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
        <p className="text-sm text-muted-foreground">
          {t("description", { count: certificates.meta.total })}
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ProofCheck rules={rules} />
        <div className="space-y-4">
          {chain && <ChainStatusCard status={chain} timeZone={timeZone} />}
          <RangeBookExport />
        </div>
      </div>

      <section className="space-y-3">
        <h2 className="text-lg font-medium">{t("certificates.title")}</h2>
        <CertificatesTable
          certificates={certificates.data}
          timeZone={timeZone}
        />
      </section>
    </>
  )
}
