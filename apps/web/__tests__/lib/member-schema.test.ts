import { describe, expect, it } from "vitest"

import { parseMemberForm } from "@/lib/member-schema"

function form(fields: Record<string, string>): FormData {
  const data = new FormData()
  for (const [key, value] of Object.entries(fields)) data.append(key, value)
  return data
}

const REQUIRED = { first_name: "Erika", last_name: "Mustermann" }

describe("parseMemberForm", () => {
  it("accepts a form with only the required fields", () => {
    /**
     * Regression: fields that are not rendered — `left_at` when creating —
     * never reach FormData at all. A schema that merely allowed null still
     * rejected the whole form, so creating a member was impossible.
     */
    const result = parseMemberForm(form(REQUIRED))

    expect(result.success).toBe(true)
    if (result.success) {
      expect(result.data.first_name).toBe("Erika")
      expect(result.data.left_at).toBeNull()
      expect(result.data.status).toBe("active")
    }
  })

  it.each(["first_name", "last_name"])("rejects a missing %s", (field) => {
    const fields = { ...REQUIRED } as Record<string, string>
    delete fields[field]

    expect(parseMemberForm(form(fields)).success).toBe(false)
  })

  it("rejects a blank name made of whitespace", () => {
    expect(
      parseMemberForm(form({ ...REQUIRED, last_name: "   " })).success
    ).toBe(false)
  })

  it("turns empty optional fields into null rather than empty strings", () => {
    // The backend distinguishes "not set" from "set to nothing"; an empty
    // string would overwrite a stored value with garbage.
    const result = parseMemberForm(
      form({ ...REQUIRED, email: "", phone: "  ", city: "" })
    )

    expect(result.success).toBe(true)
    if (result.success) {
      expect(result.data.email).toBeNull()
      expect(result.data.phone).toBeNull()
      expect(result.data.city).toBeNull()
    }
  })

  it("trims surrounding whitespace", () => {
    const result = parseMemberForm(form({ ...REQUIRED, city: "  Stuttgart  " }))

    expect(result.success).toBe(true)
    if (result.success) expect(result.data.city).toBe("Stuttgart")
  })

  it("rejects a malformed email but accepts an empty one", () => {
    expect(
      parseMemberForm(form({ ...REQUIRED, email: "not-an-email" })).success
    ).toBe(false)
    expect(parseMemberForm(form({ ...REQUIRED, email: "" })).success).toBe(true)
  })

  it("rejects a date that is not ISO formatted", () => {
    // Browsers send YYYY-MM-DD, but a hand-built request need not.
    expect(
      parseMemberForm(form({ ...REQUIRED, joined_at: "01.08.2026" })).success
    ).toBe(false)
    expect(
      parseMemberForm(form({ ...REQUIRED, joined_at: "2026-08-01" })).success
    ).toBe(true)
  })

  it("accepts a known gender and treats an empty one as null", () => {
    const result = parseMemberForm(form({ ...REQUIRED, gender: "female" }))
    expect(result.success).toBe(true)
    if (result.success) expect(result.data.gender).toBe("female")

    const empty = parseMemberForm(form({ ...REQUIRED, gender: "" }))
    expect(empty.success).toBe(true)
    if (empty.success) expect(empty.data.gender).toBeNull()

    // Not rendered at all (older cached form) must also pass.
    const absent = parseMemberForm(form(REQUIRED))
    expect(absent.success).toBe(true)
    if (absent.success) expect(absent.data.gender).toBeNull()
  })

  it("rejects a gender outside the known set", () => {
    expect(
      parseMemberForm(form({ ...REQUIRED, gender: "unbekannt" })).success
    ).toBe(false)
  })

  it("rejects a status outside the known set", () => {
    // Status drives the leaving logic, so an arbitrary value must not pass.
    expect(
      parseMemberForm(form({ ...REQUIRED, status: "vorstand" })).success
    ).toBe(false)
    expect(
      parseMemberForm(form({ ...REQUIRED, status: "resigned" })).success
    ).toBe(true)
  })
})
