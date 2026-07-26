"use client"

import { useTranslations, useLocale } from "next-intl"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useDueSummary } from "@/hooks/use-dues"
import { formatCurrency } from "@/lib/currency"

interface DuesSummaryCardsProps {
  year: number
}

export function DuesSummaryCards({ year }: DuesSummaryCardsProps) {
  const t = useTranslations("dues")
  const locale = useLocale()
  const { data, isLoading } = useDueSummary(year)

  const cards = [
    {
      key: "open",
      title: t("openAmount"),
      value: formatCurrency(data?.open_amount ?? "0", locale),
      sub: t("nItems", { count: data?.open_count ?? 0 }),
    },
    {
      key: "paid",
      title: t("paidAmount"),
      value: formatCurrency(data?.paid_amount ?? "0", locale),
      sub: t("nItems", { count: data?.paid_count ?? 0 }),
    },
  ]

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:max-w-xl">
      {cards.map((card) => (
        <Card key={card.key}>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              {card.title}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="h-8 w-24 animate-pulse rounded bg-muted" />
            ) : (
              <>
                <p className="text-2xl font-bold tabular-nums">{card.value}</p>
                <p className="text-muted-foreground mt-1 text-xs">{card.sub}</p>
              </>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
