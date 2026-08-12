/** Mirrors `app/schemas/incoming_invoice.py`. Money arrives as a decimal string. */

export type InvoiceStatus = "open" | "paid" | "cancelled"

/** Where the figures came from — a machine-readable statement, or a reading. */
export type InvoiceSource = "manual" | "zugferd" | "xrechnung"

export type IncomingInvoice = {
  id: string
  supplier_name: string | null
  supplier_vat_id: string | null
  invoice_number: string | null
  invoice_date: string | null
  due_date: string | null
  gross_amount: string | null
  net_amount: string | null
  tax_amount: string | null
  currency: string
  status: InvoiceStatus
  paid_on: string | null
  note: string | null
  source: InvoiceSource
  /** Supplier, number, date and amount — what the totals need to count it. */
  is_complete: boolean
  original_filename: string
  content_type: string
  byte_size: number
  uploaded_at: string
}

export type IncomingInvoiceSummary = {
  year: number | null
  open_count: number
  open_amount: string
  paid_count: number
  paid_amount: string
  cancelled_count: number
  cancelled_amount: string
  total_amount: string
  /** Rows the totals cannot see, because a figure is still missing. */
  incomplete_count: number
}
