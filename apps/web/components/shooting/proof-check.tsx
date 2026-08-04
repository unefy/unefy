"use client"

import { useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"
import { toast } from "sonner"

import { evaluateProofAction, issueCertificateAction } from "@/actions/shooting"
import { MemberSearch } from "@/components/attendance/member-search"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { formatDate } from "@/lib/time"
import type { Member } from "@/lib/types/member"
import type { ProofEvaluation, ShootingRule } from "@/lib/types/shooting"

/**
 * The live §14 check: pick a member and a rule, see the numbers, and — only
 * through a separate, deliberate click — issue the certificate. The
 * evaluation proposes; a person issues.
 */
export function ProofCheck({ rules }: { rules: ShootingRule[] }) {
  const t = useTranslations("shooting.proof")
  const locale = useLocale()
  const router = useRouter()

  const [member, setMember] = useState<Member | null>(null)
  const [ruleKey, setRuleKey] = useState(rules[0]?.rule_key ?? "")
  const [evaluation, setEvaluation] = useState<ProofEvaluation | null>(null)
  const [pending, startTransition] = useTransition()

  const ruleLabel = (key: string) =>
    rules.find((rule) => rule.rule_key === key)?.label ?? key

  const evaluate = () => {
    if (!member || !ruleKey) return
    startTransition(async () => {
      const result = await evaluateProofAction(member.id, ruleKey)
      if (result.success && result.data) {
        setEvaluation(result.data)
      } else if (!result.success) {
        toast.error(t(`errors.${result.error}`))
      }
    })
  }

  const issue = () => {
    if (!member || !ruleKey) return
    startTransition(async () => {
      const result = await issueCertificateAction(member.id, ruleKey)
      if (result.success) {
        toast.success(t("issuedToast"))
        setEvaluation(null)
        setMember(null)
        router.refresh()
      } else {
        toast.error(t(`errors.${result.error}`))
      }
    })
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("title")}</CardTitle>
        <CardDescription>{t("hint")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {rules.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("noRules")}</p>
        ) : (
          <>
            <div className="space-y-2">
              <Label htmlFor="proof-rule">{t("rule")}</Label>
              <Select
                value={ruleKey}
                onValueChange={(value) => {
                  setRuleKey(String(value))
                  setEvaluation(null)
                }}
              >
                <SelectTrigger id="proof-rule" className="w-full">
                  <SelectValue>
                    {(value: string) => ruleLabel(value)}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {rules.map((rule) => (
                      <SelectItem key={rule.id} value={rule.rule_key}>
                        {rule.label}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>

            {member ? (
              <div className="flex items-center justify-between gap-3 rounded-md border px-3 py-2">
                <span className="text-sm">
                  <span className="font-medium">
                    {member.last_name}, {member.first_name}
                  </span>{" "}
                  <span className="font-mono text-xs text-muted-foreground">
                    {member.member_number}
                  </span>
                </span>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setMember(null)
                    setEvaluation(null)
                  }}
                >
                  {t("changeMember")}
                </Button>
              </div>
            ) : (
              <MemberSearch
                onSelect={(selected) => {
                  setMember(selected)
                  setEvaluation(null)
                }}
                placeholder={t("memberPlaceholder")}
                actionLabel={t("pick")}
              />
            )}

            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                disabled={!member || pending}
                onClick={evaluate}
              >
                {t("evaluate")}
              </Button>
              {/* Issuing stays possible for a failed evaluation on purpose:
                  the certificate then documents "not met", which an
                  association may ask for just the same. */}
              <Button
                type="button"
                disabled={!member || evaluation === null || pending}
                onClick={issue}
              >
                {t("issue")}
              </Button>
            </div>

            {evaluation && (
              <dl className="grid grid-cols-2 gap-x-4 gap-y-2 rounded-md border p-3 text-sm">
                <dt className="text-muted-foreground">{t("result")}</dt>
                <dd>
                  {evaluation.passed ? (
                    <Badge>{t("passed")}</Badge>
                  ) : (
                    <Badge variant="destructive">{t("failed")}</Badge>
                  )}
                </dd>
                <dt className="text-muted-foreground">{t("period")}</dt>
                {/* Calendar dates, not instants — formatted in UTC so the
                    day never shifts with the viewer's zone. */}
                <dd className="tabular-nums">
                  {formatDate(evaluation.period_start, locale, "UTC")} –{" "}
                  {formatDate(evaluation.period_end, locale, "UTC")}
                </dd>
                <dt className="text-muted-foreground">{t("sessionCount")}</dt>
                <dd className="tabular-nums">{evaluation.session_count}</dd>
                <dt className="text-muted-foreground">{t("monthsCovered")}</dt>
                <dd className="tabular-nums">{evaluation.months_covered}</dd>
                {/* Only when there is something to say. A club whose supervisors
                    are always scanned by somebody has no self-entries, and a row
                    of zeroes would just train people to skip this block. */}
                {evaluation.self_certified_days > 0 && (
                  <>
                    <dt className="text-muted-foreground">
                      {t("selfCertifiedDays")}
                    </dt>
                    <dd className="tabular-nums">
                      {t("selfCertifiedValue", {
                        count: evaluation.self_certified_days,
                        corroborated: evaluation.corroborated_self_days,
                      })}
                    </dd>
                  </>
                )}
              </dl>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}
