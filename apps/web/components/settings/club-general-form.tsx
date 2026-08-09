"use client"

import { useMemo, useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import { updateClubAction } from "@/actions/club"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import type { Club } from "@/lib/types/club"

/**
 * Lifted to the top of the zone list.
 *
 * The full IANA list runs to several hundred entries, which is a lot of
 * scrolling for a club in Berlin. These cover almost every club that will ever
 * open this page; the complete list stays right below them, so nobody is
 * locked out of the rest.
 */
const COMMON_ZONES = ["Europe/Berlin", "Europe/Vienna", "Europe/Zurich"]

/** Used when the runtime cannot enumerate zones itself. */
const FALLBACK_ZONES = [...COMMON_ZONES, "UTC"]

function Field({
  id,
  label,
  hint,
  className,
  children,
}: {
  id?: string
  label: string
  hint?: string
  className?: string
  children: React.ReactNode
}) {
  return (
    <div className={className ? `space-y-2 ${className}` : "space-y-2"}>
      <Label htmlFor={id}>{label}</Label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  )
}

function Section({
  title,
  description,
  children,
}: {
  title: string
  description?: string
  children: React.ReactNode
}) {
  return (
    <section className="space-y-3">
      <div className="space-y-1">
        <h2 className="text-sm font-medium">{title}</h2>
        {description && (
          <p className="max-w-2xl text-xs text-muted-foreground">
            {description}
          </p>
        )}
      </div>
      <div className="grid gap-4 rounded-md border p-4 sm:grid-cols-2 lg:grid-cols-3">
        {children}
      </div>
    </section>
  )
}

export function ClubGeneralForm({
  club,
  canEdit,
}: {
  club: Club
  /** Only owner and admin may write; everyone else reads. */
  canEdit: boolean
}) {
  const t = useTranslations("clubSettings")
  const router = useRouter()
  const [pending, startTransition] = useTransition()

  const [timezone, setTimezone] = useState(club.timezone)
  const [isNonprofit, setIsNonprofit] = useState(club.is_nonprofit)

  // Ask the runtime for the zone list rather than shipping one: it is already
  // there, it stays current, and hard-coding a region would contradict a
  // product meant to be self-hosted anywhere.
  const { common, all } = useMemo(() => {
    const supported =
      typeof Intl.supportedValuesOf === "function"
        ? Intl.supportedValuesOf("timeZone")
        : FALLBACK_ZONES
    // The stored zone may be one the runtime does not list (an alias, say).
    // Dropping it would silently rewrite the club's setting on the next save.
    const full = supported.includes(club.timezone)
      ? supported
      : [club.timezone, ...supported]
    // The club's current zone belongs in the shortlist even when it is not one
    // of the usual ones — otherwise the one entry that matters is the one you
    // have to hunt for.
    const shortlist = [
      ...new Set(
        [club.timezone, ...COMMON_ZONES].filter((z) => full.includes(z))
      ),
    ]
    return { common: shortlist, all: full }
  }, [club.timezone])

  function submit(formData: FormData) {
    startTransition(async () => {
      const result = await updateClubAction(undefined, formData)
      if (result.success) {
        toast.success(t("savedToast"))
        router.refresh()
      } else {
        toast.error(t(`errors.${result.error}`))
      }
    })
  }

  return (
    <form action={submit} className="space-y-8">
      <fieldset disabled={!canEdit || pending} className="space-y-8">
        <Section title={t("sections.club")}>
          <Field id="name" label={t("fields.name")}>
            <Input
              id="name"
              name="name"
              required
              minLength={2}
              maxLength={255}
              defaultValue={club.name}
            />
          </Field>
          <Field
            id="short_name"
            label={t("fields.shortName")}
            hint={t("hints.shortName")}
          >
            <Input
              id="short_name"
              name="short_name"
              maxLength={50}
              defaultValue={club.short_name ?? ""}
            />
          </Field>
          <Field id="slug" label={t("fields.slug")} hint={t("hints.slug")}>
            <Input
              id="slug"
              value={club.slug}
              readOnly
              disabled
              className="font-mono"
            />
          </Field>
        </Section>

        <Section
          title={t("sections.regional")}
          description={t("hints.regional")}
        >
          <Field id="timezone" label={t("fields.timezone")}>
            {/* The select can report null on clear; there is no "no time
                zone" state, so the current one stands. */}
            <Select
              value={timezone}
              onValueChange={(value) => setTimezone(value ?? timezone)}
            >
              <SelectTrigger id="timezone" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectLabel>{t("timezoneCommon")}</SelectLabel>
                  {common.map((zone) => (
                    <SelectItem key={`common-${zone}`} value={zone}>
                      {zone}
                    </SelectItem>
                  ))}
                </SelectGroup>
                <SelectSeparator />
                <SelectGroup>
                  <SelectLabel>{t("timezoneAll")}</SelectLabel>
                  {all.map((zone) => (
                    <SelectItem key={zone} value={zone}>
                      {zone}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
            <input type="hidden" name="timezone" value={timezone} />
          </Field>
        </Section>

        <Section title={t("sections.contact")}>
          <Field id="email" label={t("fields.email")}>
            <Input
              id="email"
              name="email"
              type="email"
              maxLength={255}
              defaultValue={club.email ?? ""}
            />
          </Field>
          <Field id="phone" label={t("fields.phone")}>
            <Input
              id="phone"
              name="phone"
              maxLength={50}
              defaultValue={club.phone ?? ""}
            />
          </Field>
          <Field id="website" label={t("fields.website")}>
            <Input
              id="website"
              name="website"
              maxLength={500}
              defaultValue={club.website ?? ""}
            />
          </Field>
        </Section>

        <Section title={t("sections.address")}>
          <Field
            id="street"
            label={t("fields.street")}
            className="sm:col-span-2 lg:col-span-3"
          >
            <Input
              id="street"
              name="street"
              maxLength={255}
              defaultValue={club.street ?? ""}
            />
          </Field>
          <Field id="zip_code" label={t("fields.zipCode")}>
            <Input
              id="zip_code"
              name="zip_code"
              maxLength={20}
              defaultValue={club.zip_code ?? ""}
            />
          </Field>
          <Field id="city" label={t("fields.city")}>
            <Input
              id="city"
              name="city"
              maxLength={255}
              defaultValue={club.city ?? ""}
            />
          </Field>
          <Field id="state" label={t("fields.state")}>
            <Input
              id="state"
              name="state"
              maxLength={255}
              defaultValue={club.state ?? ""}
            />
          </Field>
          <Field id="country" label={t("fields.country")}>
            <Input
              id="country"
              name="country"
              maxLength={100}
              defaultValue={club.country ?? ""}
            />
          </Field>
        </Section>

        <Section title={t("sections.legal")} description={t("hints.legal")}>
          <Field id="founded_at" label={t("fields.foundedAt")}>
            <Input
              id="founded_at"
              name="founded_at"
              type="date"
              defaultValue={club.founded_at ?? ""}
            />
          </Field>
          <Field
            id="registration_number"
            label={t("fields.registrationNumber")}
          >
            <Input
              id="registration_number"
              name="registration_number"
              maxLength={100}
              defaultValue={club.registration_number ?? ""}
            />
          </Field>
          <Field id="registration_court" label={t("fields.registrationCourt")}>
            <Input
              id="registration_court"
              name="registration_court"
              maxLength={255}
              defaultValue={club.registration_court ?? ""}
            />
          </Field>
          <Field id="tax_number" label={t("fields.taxNumber")}>
            <Input
              id="tax_number"
              name="tax_number"
              maxLength={100}
              defaultValue={club.tax_number ?? ""}
            />
          </Field>
          <Field id="tax_office" label={t("fields.taxOffice")}>
            <Input
              id="tax_office"
              name="tax_office"
              maxLength={255}
              defaultValue={club.tax_office ?? ""}
            />
          </Field>
          <div className="space-y-2">
            <Label htmlFor="is_nonprofit">{t("fields.isNonprofit")}</Label>
            <div className="flex h-9 items-center gap-3">
              <Switch
                id="is_nonprofit"
                checked={isNonprofit}
                onCheckedChange={(checked) => setIsNonprofit(checked === true)}
              />
              <span className="text-sm text-muted-foreground">
                {isNonprofit ? t("yes") : t("no")}
              </span>
            </div>
            <input
              type="hidden"
              name="is_nonprofit"
              value={isNonprofit ? "on" : ""}
            />
          </div>
          {isNonprofit && (
            <Field id="nonprofit_since" label={t("fields.nonprofitSince")}>
              <Input
                id="nonprofit_since"
                name="nonprofit_since"
                type="date"
                defaultValue={club.nonprofit_since ?? ""}
              />
            </Field>
          )}
        </Section>

        <Section title={t("sections.sepa")} description={t("hints.sepa")}>
          <Field
            id="sepa_creditor_id"
            label={t("fields.sepaCreditorId")}
            hint={t("hints.sepaCreditorId")}
          >
            <Input
              id="sepa_creditor_id"
              name="sepa_creditor_id"
              maxLength={35}
              defaultValue={club.sepa_creditor_id ?? ""}
              placeholder="DE98ZZZ09999999999"
            />
          </Field>
          <Field id="club_iban" label={t("fields.iban")}>
            <Input
              id="club_iban"
              name="iban"
              maxLength={34}
              defaultValue={club.iban ?? ""}
            />
          </Field>
          <Field id="club_bic" label={t("fields.bic")}>
            <Input
              id="club_bic"
              name="bic"
              maxLength={11}
              defaultValue={club.bic ?? ""}
            />
          </Field>
        </Section>
      </fieldset>

      {canEdit ? (
        <div className="flex justify-end">
          <Button type="submit" disabled={pending}>
            {pending ? t("saving") : t("save")}
          </Button>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">{t("readOnly")}</p>
      )}
    </form>
  )
}
