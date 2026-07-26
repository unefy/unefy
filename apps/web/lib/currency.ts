/**
 * Formats a decimal amount string (e.g. "120.00" from the API) as EUR
 * for the given locale. Returns an empty string for invalid input.
 */
export function formatCurrency(amount: string | null | undefined, locale: string): string {
  if (amount === null || amount === undefined || amount === "") return ""
  const value = Number(amount)
  if (Number.isNaN(value)) return ""
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency: "EUR",
  }).format(value)
}
