import { getTranslations } from "next-intl/server"

import { DonationReceipts } from "@/components/dues/donation-receipts"
import { getDonationReadiness, listReceipts } from "@/lib/donations"
import { listAllMembers } from "@/lib/members"

/** Donation receipts — the prescribed form, and what has been issued. */
export default async function DonationsPage() {
  const [t, receipts, readiness, members] = await Promise.all([
    getTranslations("donations"),
    listReceipts().catch(() => []),
    getDonationReadiness().catch(() => ({
      ready: false,
      missing: ["club"],
      membership_fees_deductible: false,
    })),
    // The full list, not the directory: the directory leaves out members who
    // refused to be listed, and a donor must not vanish for that reason.
    listAllMembers()
      .then((result) => result.data)
      .catch(() => []),
  ])

  return (
    <>
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
        <p className="max-w-3xl text-sm text-muted-foreground">
          {t("description")}
        </p>
      </div>

      <DonationReceipts
        receipts={receipts}
        readiness={readiness}
        members={members}
      />
    </>
  )
}
