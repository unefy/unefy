import { notFound } from "next/navigation"
import Link from "next/link"
import { getLocale, getTranslations } from "next-intl/server"

import { HeaderScrollTitle } from "@/components/layout/header-scroll-title"
import { InvoiceDetail } from "@/components/invoices/invoice-detail"
import { getClubTimeZone } from "@/lib/attendance"
import { getIncomingInvoice } from "@/lib/incoming-invoices"
import { formatDateTime } from "@/lib/time"

/**
 * One invoice, and everything the club may do with it.
 *
 * A page rather than a panel beside the list: the register is read row by row
 * and completed field by field, and a drawer over the table would put the
 * document and the form in the same eyeful as forty other invoices.
 */
export default async function IncomingInvoicePage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  const [t, locale, timeZone, invoice] = await Promise.all([
    getTranslations("invoices"),
    getLocale(),
    getClubTimeZone(),
    getIncomingInvoice(id).catch(() => null),
  ])
  if (invoice === null) notFound()

  const title = invoice.supplier_name ?? invoice.original_filename

  return (
    <>
      <div className="space-y-1">
        <HeaderScrollTitle title={title} />
        <Link
          href="/incoming-invoices"
          className="text-sm text-muted-foreground hover:underline"
        >
          {t("back")}
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        <p className="text-sm text-muted-foreground">
          {t("uploadedAt", {
            file: invoice.original_filename,
            when: formatDateTime(invoice.uploaded_at, locale, timeZone),
          })}
        </p>
      </div>

      <InvoiceDetail invoice={invoice} />
    </>
  )
}
