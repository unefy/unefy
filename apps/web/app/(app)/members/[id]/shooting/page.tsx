import { getTranslations } from "next-intl/server"

import { Badge } from "@/components/ui/badge"
import { evaluateProof, listShootingRules } from "@/lib/shooting"

/**
 * Shooting tab: the member's standing against every proof rule the club has.
 *
 * Live numbers, not certificates — issuing a frozen certificate stays on the
 * shooting module's own pages, where the proof-check flow lives.
 */
export default async function MemberShootingPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const [t, { id }] = await Promise.all([
    getTranslations("members.detail.shootingTab"),
    params,
  ])

  const rules = await listShootingRules().catch(() => [])
  const evaluations = await Promise.all(
    rules.map(async (rule) => ({
      rule,
      evaluation: await evaluateProof(id, rule.rule_key).catch(() => null),
    }))
  )

  return (
    <section className="space-y-3">
      <h2 className="text-sm font-medium text-muted-foreground">
        {t("title")}
      </h2>

      {evaluations.length === 0 ? (
        <div className="rounded-md border p-4 text-sm text-muted-foreground">
          {t("noRules")}
        </div>
      ) : (
        <div className="space-y-3">
          {evaluations.map(({ rule, evaluation }) => (
            <div key={rule.id} className="space-y-2 rounded-md border p-4">
              <div className="flex flex-wrap items-center gap-3">
                <span className="text-sm font-medium">{rule.label}</span>
                {evaluation && (
                  <Badge
                    variant={evaluation.passed ? "secondary" : "destructive"}
                  >
                    {evaluation.passed ? t("passed") : t("notPassed")}
                  </Badge>
                )}
              </div>
              {evaluation ? (
                <p className="text-sm text-muted-foreground">
                  {t("numbers", {
                    days: evaluation.session_count,
                    months: evaluation.months_covered,
                    from: evaluation.period_start,
                    to: evaluation.period_end,
                  })}
                  {evaluation.self_certified_days > 0 &&
                    " · " +
                      t("selfCertified", {
                        days: evaluation.self_certified_days,
                      })}
                </p>
              ) : (
                <p className="text-sm text-muted-foreground">
                  {t("evaluationFailed")}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
