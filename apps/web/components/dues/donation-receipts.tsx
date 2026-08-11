"use client"

import { useRouter } from "next/navigation"
import { useState, useTransition } from "react"
import { useLocale, useTranslations } from "next-intl"
import { toast } from "sonner"

import { issueReceiptAction, revokeReceiptAction } from "@/actions/donations"
import { ReasonDialog } from "@/components/attendance/reason-dialog"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button, buttonVariants } from "@/components/ui/button"
import { DataTable, type DataTableColumn } from "@/components/ui/data-table"
import { DateCell } from "@/components/ui/date-cell"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import type { Member } from "@/lib/types/member"
import type {
  DonationKind,
  DonationReadiness,
  DonationReceipt,
} from "@/lib/types/donation"
import { AlertTriangleIcon, DownloadIcon, InfoIcon } from "lucide-react"

const NO_MEMBER = "none"

/**
 * Recording a donation and issuing the receipt for it.
 *
 * The form only appears when the club's tax data is complete: the receipt
 * names the notice that recognises the club, and one that leaves those blank
 * looks official while asserting nothing.
 */
export function DonationReceipts({
  receipts,
  readiness,
  members,
}: {
  receipts: DonationReceipt[]
  readiness: DonationReadiness
  members: Member[]
}) {
  const t = useTranslations("donations")
  const locale = useLocale()
  const router = useRouter()
  const [pending, startTransition] = useTransition()

  const [memberId, setMemberId] = useState(NO_MEMBER)
  const [donorName, setDonorName] = useState("")
  const [donorAddress, setDonorAddress] = useState("")
  const [amount, setAmount] = useState("")
  const [receivedOn, setReceivedOn] = useState("")
  const [kind, setKind] = useState<DonationKind>("geldzuwendung")
  const [waiver, setWaiver] = useState(false)

  function issue() {
    startTransition(async () => {
      const result = await issueReceiptAction({
        member_id: memberId === NO_MEMBER ? null : memberId,
        donor_name: memberId === NO_MEMBER ? donorName : null,
        donor_address: memberId === NO_MEMBER ? donorAddress || null : null,
        amount,
        received_on: receivedOn,
        kind,
        is_expense_waiver: waiver,
      })
      if (!result.success) {
        toast.error(t(`errors.${result.error}`))
        return
      }
      toast.success(t("issued"))
      setAmount("")
      setDonorName("")
      setDonorAddress("")
      router.refresh()
    })
  }

  const columns: DataTableColumn<DonationReceipt>[] = [
    {
      key: "donor_name",
      header: t("columns.donor"),
      cell: (row) => <span className="font-medium">{row.donor_name}</span>,
      sortValue: (row) => row.donor_name,
    },
    {
      key: "amount",
      header: t("columns.amount"),
      cell: (row) => (
        <span className="tabular-nums">
          {Number(row.amount).toLocaleString(locale, {
            style: "currency",
            currency: "EUR",
          })}
        </span>
      ),
      sortValue: (row) => Number(row.amount),
      align: "right",
      shrink: true,
    },
    {
      key: "received_on",
      header: t("columns.receivedOn"),
      cell: (row) => <DateCell value={row.received_on} dateOnly />,
      sortValue: (row) => row.received_on,
      shrink: true,
    },
    {
      key: "kind",
      header: t("columns.kind"),
      cell: (row) => t(`kinds.${row.kind}`),
      sortValue: (row) => row.kind,
      shrink: true,
    },
    {
      key: "status",
      header: t("columns.status"),
      cell: (row) =>
        row.revoked_at ? (
          <Badge variant="outline">{t("revoked")}</Badge>
        ) : (
          <Badge>{t("valid")}</Badge>
        ),
      sortValue: (row) => (row.revoked_at ? 1 : 0),
      shrink: true,
    },
    {
      key: "actions",
      header: "",
      cell: (row) => (
        <div className="flex items-center justify-end gap-1">
          <a
            href={`/api/donations/${row.id}/pdf`}
            className={buttonVariants({ variant: "ghost", size: "sm" })}
            aria-label={t("download")}
          >
            <DownloadIcon className="size-4" />
          </a>
          {row.revoked_at ? null : (
            <ReasonDialog
              title={t("confirmRevoke.title")}
              description={t("confirmRevoke.description")}
              confirmLabel={t("revoke")}
              successMessage={t("revokedToast")}
              action={(reason) => revokeReceiptAction(row.id, reason)}
              trigger={
                <span
                  className={buttonVariants({ variant: "ghost", size: "sm" })}
                >
                  {t("revoke")}
                </span>
              }
            />
          )}
        </div>
      ),
      shrink: true,
    },
  ]

  return (
    <div className="space-y-6">
      {readiness.ready ? null : (
        <Alert>
          <AlertTriangleIcon />
          <AlertDescription>
            {t("notReady")}{" "}
            <a className="underline underline-offset-4" href="/settings">
              {t("toSettings")}
            </a>
            <span className="mt-1 block text-xs">
              {readiness.missing
                .map((field) => t(`missing.${field}`))
                .join(", ")}
            </span>
          </AlertDescription>
        </Alert>
      )}

      {readiness.ready ? (
        <section className="space-y-4 rounded-lg border p-4">
          <div className="space-y-1">
            <h2 className="text-sm font-medium">{t("issueTitle")}</h2>
            <p className="max-w-3xl text-sm text-muted-foreground">
              {t("issueHint")}
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <div className="space-y-2">
              <Label htmlFor="donation-member">{t("fields.member")}</Label>
              <Select
                name="member"
                value={memberId}
                onValueChange={(value) => setMemberId(String(value))}
              >
                <SelectTrigger id="donation-member">
                  <SelectValue>
                    {(value: string) =>
                      value === NO_MEMBER
                        ? t("noMember")
                        : (members.find((m) => m.id === value)?.last_name ?? "")
                    }
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NO_MEMBER}>{t("noMember")}</SelectItem>
                  {members.map((member) => (
                    <SelectItem key={member.id} value={member.id}>
                      {member.last_name}, {member.first_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                {t("hints.member")}
              </p>
            </div>

            {memberId === NO_MEMBER ? (
              <>
                <div className="space-y-2">
                  <Label htmlFor="donation-donor">{t("fields.donor")}</Label>
                  <Input
                    id="donation-donor"
                    value={donorName}
                    maxLength={255}
                    onChange={(e) => setDonorName(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="donation-address">
                    {t("fields.donorAddress")}
                  </Label>
                  <Input
                    id="donation-address"
                    value={donorAddress}
                    maxLength={500}
                    onChange={(e) => setDonorAddress(e.target.value)}
                  />
                </div>
              </>
            ) : null}

            <div className="space-y-2">
              <Label htmlFor="donation-amount">{t("fields.amount")}</Label>
              <Input
                id="donation-amount"
                inputMode="decimal"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="250,00"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="donation-date">{t("fields.receivedOn")}</Label>
              <Input
                id="donation-date"
                type="date"
                value={receivedOn}
                onChange={(e) => setReceivedOn(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="donation-kind">{t("fields.kind")}</Label>
              <Select
                name="kind"
                value={kind}
                onValueChange={(value) => setKind(value as DonationKind)}
              >
                <SelectTrigger id="donation-kind">
                  <SelectValue>
                    {(value: string) => t(`kinds.${value}`)}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="geldzuwendung">
                    {t("kinds.geldzuwendung")}
                  </SelectItem>
                  {/* Only offered when the club has said its recognised
                      purposes allow it — for a sports club they do not. */}
                  {readiness.membership_fees_deductible ? (
                    <SelectItem value="mitgliedsbeitrag">
                      {t("kinds.mitgliedsbeitrag")}
                    </SelectItem>
                  ) : null}
                </SelectContent>
              </Select>
              {readiness.membership_fees_deductible ? null : (
                <p className="text-xs text-muted-foreground">
                  {t("hints.feesNotDeductible")}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="donation-waiver">{t("fields.waiver")}</Label>
              <div className="flex h-9 items-center gap-3">
                <Switch
                  id="donation-waiver"
                  checked={waiver}
                  onCheckedChange={(checked) => setWaiver(checked === true)}
                />
                <span className="text-sm text-muted-foreground">
                  {waiver ? t("yes") : t("no")}
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                {t("hints.waiver")}
              </p>
            </div>
          </div>

          <div className="flex justify-end">
            <Button
              onClick={issue}
              disabled={pending || !amount || !receivedOn}
            >
              {pending ? t("issuing") : t("issue")}
            </Button>
          </div>
        </section>
      ) : null}

      <section className="space-y-3">
        <h2 className="text-sm font-medium">{t("historyTitle")}</h2>
        <DataTable
          data={receipts}
          columns={columns}
          rowKey={(row) => row.id}
          searchPlaceholder={t("search")}
          searchFields={(row) => [row.donor_name]}
          defaultSort={{ key: "received_on", direction: "desc" }}
          emptyText={t("empty")}
          noMatchText={t("noMatch")}
          locale={locale}
        />
        <p className="flex items-start gap-2 text-xs text-muted-foreground">
          <InfoIcon className="mt-0.5 size-3.5 shrink-0" />
          <span>{t("historyNote")}</span>
        </p>
      </section>
    </div>
  )
}
