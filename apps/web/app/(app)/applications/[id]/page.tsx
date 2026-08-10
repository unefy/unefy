import Link from "next/link"
import { notFound } from "next/navigation"
import { getTranslations } from "next-intl/server"

import { ApplicationDecision } from "@/components/members/application-decision"
import { Badge } from "@/components/ui/badge"
import { DateCell } from "@/components/ui/date-cell"
import { getApplication } from "@/lib/applications"
import { listClubDivisions } from "@/lib/functions"
import { listFeeTypes } from "@/lib/dues"
import { genderLabel } from "@/lib/labels"

function Fact({
  label,
  value,
  children,
}: {
  label: string
  value?: string | null
  children?: React.ReactNode
}) {
  return (
    <div className="space-y-1">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-sm">{children ?? (value?.trim() ? value : "—")}</dd>
    </div>
  )
}

function Section({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <section className="space-y-3 rounded-lg border p-4">
      <h2 className="text-sm font-medium">{title}</h2>
      <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{children}</dl>
    </section>
  )
}

/** One application: everything the applicant said, and the two buttons. */
export default async function ApplicationPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const [t, tg, { id }] = await Promise.all([
    getTranslations("applications"),
    // Gender labels live in the admin namespace, next to the other enums.
    getTranslations("admin"),
    params,
  ])

  const application = await getApplication(id).catch(() => null)
  if (!application) notFound()

  // Names for the two ids the applicant chose. Failing to resolve them must
  // not hide the application — the decision does not depend on the labels.
  const [feeTypes, divisions] = await Promise.all([
    application.fee_type_id ? listFeeTypes().catch(() => []) : [],
    application.division_id ? listClubDivisions().catch(() => []) : [],
  ])
  const feeType = feeTypes.find((f) => f.id === application.fee_type_id)
  const division = divisions.find((d) => d.id === application.division_id)

  const address = [
    application.street,
    [application.zip_code, application.city].filter(Boolean).join(" "),
    application.country,
  ]
    .filter((line) => line && line.trim())
    .join(", ")

  const consents = [
    application.consent_photos ? t("consents.photos") : null,
    application.consent_newsletter ? t("consents.newsletter") : null,
    application.consent_directory ? t("consents.directory") : null,
  ].filter(Boolean)

  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">
            {application.first_name} {application.last_name}
          </h1>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Badge
              variant={
                application.status === "pending" ? "default" : "secondary"
              }
            >
              {t(`status.${application.status}`)}
            </Badge>
            <span>
              {t("receivedOn")} <DateCell value={application.created_at} />
            </span>
          </div>
        </div>

        {application.status === "pending" ? (
          <ApplicationDecision
            applicationId={application.id}
            applicantName={`${application.first_name} ${application.last_name}`}
          />
        ) : application.member_id ? (
          <Link
            className="text-sm underline underline-offset-4"
            href={`/members/${application.member_id}`}
          >
            {t("toMember")}
          </Link>
        ) : null}
      </div>

      {application.message ? (
        <section className="space-y-2 rounded-lg border bg-muted/40 p-4">
          <h2 className="text-sm font-medium">{t("message")}</h2>
          <p className="text-sm whitespace-pre-wrap">{application.message}</p>
        </section>
      ) : null}

      <Section title={t("sections.person")}>
        <Fact label={t("fields.firstName")} value={application.first_name} />
        <Fact label={t("fields.lastName")} value={application.last_name} />
        <Fact label={t("fields.birthday")}>
          <DateCell value={application.birthday} dateOnly />
        </Fact>
        <Fact
          label={t("fields.gender")}
          value={
            application.gender ? genderLabel(tg, application.gender) : null
          }
        />
      </Section>

      <Section title={t("sections.contact")}>
        <Fact label={t("fields.email")} value={application.email} />
        <Fact label={t("fields.phone")} value={application.phone} />
        <Fact label={t("fields.mobile")} value={application.mobile} />
        <Fact label={t("fields.address")} value={address} />
      </Section>

      <Section title={t("sections.membership")}>
        <Fact
          label={t("fields.feeType")}
          value={feeType?.name ?? (application.fee_type_id ? "—" : null)}
        />
        <Fact
          label={t("fields.division")}
          value={division?.name ?? (application.division_id ? "—" : null)}
        />
      </Section>

      <Section title={t("sections.payment")}>
        <Fact label={t("fields.iban")} value={application.iban} />
        <Fact label={t("fields.bic")} value={application.bic} />
        <Fact
          label={t("fields.accountHolder")}
          value={application.account_holder}
        />
        <Fact label={t("fields.mandate")}>
          {application.has_sepa_mandate ? t("mandateGranted") : "—"}
        </Fact>
      </Section>

      <Section title={t("sections.privacy")}>
        <Fact label={t("fields.privacyAccepted")}>
          <DateCell value={application.privacy_accepted_at} />
        </Fact>
        <Fact
          label={t("fields.consents")}
          value={consents.length ? consents.join(", ") : t("noConsents")}
        />
      </Section>

      {application.status !== "pending" ? (
        <Section title={t("sections.decision")}>
          <Fact label={t("fields.decidedAt")}>
            <DateCell value={application.decided_at} />
          </Fact>
          <Fact
            label={t("fields.decisionNote")}
            value={application.decision_note}
          />
        </Section>
      ) : null}
    </>
  )
}
