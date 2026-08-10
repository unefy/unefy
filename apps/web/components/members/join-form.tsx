"use client"

import { useActionState, useState } from "react"
import { useTranslations } from "next-intl"

import { submitApplicationAction } from "@/actions/applications"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import type { JoinForm as JoinFormData } from "@/lib/types/application"
import { CheckCircle2Icon } from "lucide-react"

function Row({
  label,
  name,
  type = "text",
  required = false,
  autoComplete,
}: {
  label: string
  name: string
  type?: string
  required?: boolean
  autoComplete?: string
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={name}>
        {label}
        {required ? <span aria-hidden> *</span> : null}
      </Label>
      <Input
        id={name}
        name={name}
        type={type}
        required={required}
        autoComplete={autoComplete}
      />
    </div>
  )
}

/**
 * The public join form.
 *
 * Everything past the name is optional, including the e-mail: a club that
 * wants a phone number instead should get one rather than a made-up address.
 * The privacy box is the single hard requirement, because without it there is
 * no lawful basis to keep what was typed above it.
 */
export function JoinForm({ slug, form }: { slug: string; form: JoinFormData }) {
  const t = useTranslations("join")
  const [state, action, pending] = useActionState(
    submitApplicationAction.bind(null, slug),
    undefined
  )
  const [wantsMandate, setWantsMandate] = useState(false)
  const [privacyAccepted, setPrivacyAccepted] = useState(false)

  // Only after a submit attempt — flagging an empty box before anybody tried
  // to send anything is nagging, not help.
  const missingPrivacy = Boolean(state && !state.success && !privacyAccepted)

  if (state?.success) {
    return (
      <div className="space-y-3 rounded-lg border bg-muted/40 p-6 text-center">
        <CheckCircle2Icon className="mx-auto size-8 text-muted-foreground" />
        <h2 className="text-lg font-medium">{t("done.title")}</h2>
        <p className="text-sm text-muted-foreground">
          {t("done.description", { club: form.club_name })}
        </p>
      </div>
    )
  }

  return (
    <form action={action} className="space-y-8">
      <fieldset className="space-y-4" disabled={pending}>
        <legend className="text-sm font-medium">{t("sections.person")}</legend>
        <div className="grid gap-4 sm:grid-cols-2">
          <Row label={t("fields.firstName")} name="first_name" required />
          <Row label={t("fields.lastName")} name="last_name" required />
          <Row label={t("fields.birthday")} name="birthday" type="date" />
          <div className="space-y-2">
            <Label htmlFor="gender">{t("fields.gender")}</Label>
            <Select name="gender">
              <SelectTrigger id="gender">
                <SelectValue placeholder={t("noAnswer")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="female">{t("gender.female")}</SelectItem>
                <SelectItem value="male">{t("gender.male")}</SelectItem>
                <SelectItem value="diverse">{t("gender.diverse")}</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </fieldset>

      <fieldset className="space-y-4" disabled={pending}>
        <legend className="text-sm font-medium">{t("sections.contact")}</legend>
        <div className="grid gap-4 sm:grid-cols-2">
          <Row
            label={t("fields.email")}
            name="email"
            type="email"
            autoComplete="email"
          />
          <Row label={t("fields.mobile")} name="mobile" autoComplete="tel" />
          <Row
            label={t("fields.street")}
            name="street"
            autoComplete="street-address"
          />
          <div className="grid grid-cols-[7rem_1fr] gap-4">
            <Row
              label={t("fields.zipCode")}
              name="zip_code"
              autoComplete="postal-code"
            />
            <Row
              label={t("fields.city")}
              name="city"
              autoComplete="address-level2"
            />
          </div>
        </div>
      </fieldset>

      {form.fee_types.length > 0 || form.divisions.length > 0 ? (
        <fieldset className="space-y-4" disabled={pending}>
          <legend className="text-sm font-medium">
            {t("sections.membership")}
          </legend>
          <div className="grid gap-4 sm:grid-cols-2">
            {form.fee_types.length > 0 ? (
              <div className="space-y-2">
                <Label htmlFor="fee_type_id">{t("fields.feeType")}</Label>
                <Select name="fee_type_id">
                  <SelectTrigger id="fee_type_id">
                    <SelectValue placeholder={t("chooseLater")} />
                  </SelectTrigger>
                  <SelectContent>
                    {form.fee_types.map((fee) => (
                      <SelectItem key={fee.id} value={fee.id}>
                        {fee.name} — {fee.amount} €{" "}
                        {t(`interval.${fee.interval}`)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            ) : null}
            {form.divisions.length > 0 ? (
              <div className="space-y-2">
                <Label htmlFor="division_id">{t("fields.division")}</Label>
                <Select name="division_id">
                  <SelectTrigger id="division_id">
                    <SelectValue placeholder={t("chooseLater")} />
                  </SelectTrigger>
                  <SelectContent>
                    {form.divisions.map((division) => (
                      <SelectItem key={division.id} value={division.id}>
                        {division.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            ) : null}
          </div>
        </fieldset>
      ) : null}

      <fieldset className="space-y-4" disabled={pending}>
        <legend className="text-sm font-medium">{t("sections.payment")}</legend>
        <div className="flex items-start gap-3">
          <Checkbox
            id="grant_sepa_mandate"
            name="grant_sepa_mandate"
            checked={wantsMandate}
            onCheckedChange={(checked) => setWantsMandate(checked === true)}
          />
          <Label
            htmlFor="grant_sepa_mandate"
            className="text-sm leading-relaxed font-normal"
          >
            {t("mandate.label", { club: form.club_name })}
          </Label>
        </div>
        {wantsMandate ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <Row label={t("fields.iban")} name="iban" required />
            <Row label={t("fields.bic")} name="bic" />
            <Row label={t("fields.accountHolder")} name="account_holder" />
          </div>
        ) : null}
      </fieldset>

      <fieldset className="space-y-4" disabled={pending}>
        <legend className="text-sm font-medium">{t("sections.message")}</legend>
        <Textarea name="message" rows={4} maxLength={2000} />
      </fieldset>

      <fieldset className="space-y-4" disabled={pending}>
        <legend className="text-sm font-medium">{t("sections.privacy")}</legend>
        {/* Checked here rather than with the native `required`: the checkbox
            renders its form input visually hidden, and a browser cannot focus
            a hidden invalid control — it refuses the submit and shows nothing.
            Our own message says which box is missing. */}
        <div className="space-y-2">
          <div className="flex items-start gap-3">
            <Checkbox
              id="privacy_accepted"
              name="privacy_accepted"
              checked={privacyAccepted}
              onCheckedChange={(checked) =>
                setPrivacyAccepted(checked === true)
              }
              aria-invalid={missingPrivacy}
            />
            <Label
              htmlFor="privacy_accepted"
              className="text-sm leading-relaxed font-normal"
            >
              {t("privacy.label")} <span aria-hidden>*</span>
            </Label>
          </div>
          {missingPrivacy ? (
            <p className="text-sm text-destructive">{t("privacy.required")}</p>
          ) : null}
        </div>

        {/* Separate from the box above on purpose: a consent that is bundled
            with a precondition is not freely given, and not valid. */}
        <div className="space-y-3 rounded-lg border p-4">
          <p className="text-xs text-muted-foreground">{t("consents.intro")}</p>
          {(["photos", "newsletter", "directory"] as const).map((key) => (
            <div key={key} className="flex items-start gap-3">
              <Checkbox id={`consent_${key}`} name={`consent_${key}`} />
              <Label
                htmlFor={`consent_${key}`}
                className="text-sm leading-relaxed font-normal"
              >
                {t(`consents.${key}`)}
              </Label>
            </div>
          ))}
        </div>
      </fieldset>

      {state && !state.success ? (
        <p className="text-sm text-destructive">{t(`errors.${state.error}`)}</p>
      ) : null}

      <Button type="submit" disabled={pending} className="w-full sm:w-auto">
        {pending ? t("submitting") : t("submit")}
      </Button>
      <p className="text-xs text-muted-foreground">{t("footnote")}</p>
    </form>
  )
}
