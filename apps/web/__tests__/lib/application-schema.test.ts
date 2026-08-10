import { describe, expect, it } from "vitest"

import { parseApplicationForm } from "@/lib/application-schema"

function form(fields: Record<string, string>): FormData {
  const data = new FormData()
  for (const [key, value] of Object.entries(fields)) data.append(key, value)
  return data
}

/** What a browser actually sends: ticked boxes appear with "on", unticked
 * boxes do not appear at all. */
const MINIMUM = {
  first_name: "Jonas",
  last_name: "Weber",
  privacy_accepted: "on",
}

describe("parseApplicationForm", () => {
  it("accepts a form with only the required fields", () => {
    const result = parseApplicationForm(form(MINIMUM))

    expect(result.success).toBe(true)
    if (result.success) {
      expect(result.data.first_name).toBe("Jonas")
      expect(result.data.privacy_accepted).toBe(true)
      // Missing checkboxes are false, not undefined — the backend stores them
      // as recorded refusals rather than as "not asked".
      expect(result.data.consent_photos).toBe(false)
      expect(result.data.email).toBeNull()
    }
  })

  it("rejects a form without the privacy confirmation", () => {
    /**
     * The one hard requirement. Checked here as well as in the backend so the
     * applicant is told which box is missing rather than being handed a
     * generic error after a full round trip.
     */
    const fields = { ...MINIMUM } as Record<string, string>
    delete fields.privacy_accepted

    expect(parseApplicationForm(form(fields)).success).toBe(false)
  })

  it.each(["first_name", "last_name"])("rejects a missing %s", (field) => {
    const fields = { ...MINIMUM } as Record<string, string>
    delete fields[field]

    expect(parseApplicationForm(form(fields)).success).toBe(false)
  })

  it("rejects a mandate without an account", () => {
    expect(
      parseApplicationForm(form({ ...MINIMUM, grant_sepa_mandate: "on" }))
        .success
    ).toBe(false)

    expect(
      parseApplicationForm(
        form({
          ...MINIMUM,
          grant_sepa_mandate: "on",
          iban: "DE02120300000000202051",
        })
      ).success
    ).toBe(true)
  })

  it("turns the unset selects into null rather than an empty string", () => {
    /**
     * The select renders a hidden input that is present but empty when nothing
     * was chosen. Passed through as "" it would reach the backend as an
     * invalid uuid and fail the whole form.
     */
    const result = parseApplicationForm(
      form({ ...MINIMUM, fee_type_id: "", division_id: "", gender: "" })
    )

    expect(result.success).toBe(true)
    if (result.success) {
      expect(result.data.fee_type_id).toBeNull()
      expect(result.data.division_id).toBeNull()
      expect(result.data.gender).toBeNull()
    }
  })

  it("rejects an id that is not a uuid", () => {
    expect(
      parseApplicationForm(form({ ...MINIMUM, fee_type_id: "erwachsene" }))
        .success
    ).toBe(false)
  })

  it("rejects an address that is not an e-mail", () => {
    expect(
      parseApplicationForm(form({ ...MINIMUM, email: "jonas.weber" })).success
    ).toBe(false)
  })
})
