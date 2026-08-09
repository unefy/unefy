import { describe, expect, it } from "vitest"

import {
  parseAssignmentForm,
  parseFeeTypeForm,
  parsePaymentForm,
  sepaExportQuerySchema,
} from "@/lib/due-schema"

function form(fields: Record<string, string>): FormData {
  const data = new FormData()
  for (const [key, value] of Object.entries(fields)) data.append(key, value)
  return data
}

const FEE = { name: "Jahresbeitrag", amount: "60,00", interval: "yearly" }
const ASSIGNMENT = {
  member_id: "3f6b8f4e-1a2b-4c3d-8e9f-0a1b2c3d4e5f",
  fee_type_id: "4a7c9f5e-2b3c-4d5e-9f0a-1b2c3d4e5f60",
  valid_from: "2026-01-01",
}

describe("parseFeeTypeForm", () => {
  it("accepts a comma as the decimal separator", () => {
    const result = parseFeeTypeForm(form(FEE))
    expect(result.success).toBe(true)
    // The API wants a dot; a treasurer types a comma.
    if (result.success) expect(result.data.amount).toBe("60.00")
  })

  it("keeps the amount a string", () => {
    const result = parseFeeTypeForm(form({ ...FEE, amount: "12.30" }))
    expect(result.success).toBe(true)
    if (result.success) expect(result.data.amount).toBe("12.30")
  })

  it("rejects amounts that are not money", () => {
    for (const amount of ["", "abc", "1,234", "-5", "1.2.3"]) {
      expect(parseFeeTypeForm(form({ ...FEE, amount })).success).toBe(false)
    }
  })

  it("accepts zero — a free membership is a fee type too", () => {
    expect(parseFeeTypeForm(form({ ...FEE, amount: "0" })).success).toBe(true)
  })

  it("rejects an unknown interval", () => {
    expect(
      parseFeeTypeForm(form({ ...FEE, interval: "weekly" })).success
    ).toBe(false)
  })
})

describe("parseAssignmentForm", () => {
  it("accepts an open-ended assignment", () => {
    const result = parseAssignmentForm(form(ASSIGNMENT))
    expect(result.success).toBe(true)
    if (result.success) expect(result.data.valid_to).toBeNull()
  })

  it("rejects an end before the start", () => {
    const result = parseAssignmentForm(
      form({ ...ASSIGNMENT, valid_to: "2025-12-31" })
    )
    expect(result.success).toBe(false)
  })

  it("accepts an end on the start date", () => {
    expect(
      parseAssignmentForm(form({ ...ASSIGNMENT, valid_to: "2026-01-01" }))
        .success
    ).toBe(true)
  })

  it("rejects a non-uuid member", () => {
    expect(
      parseAssignmentForm(form({ ...ASSIGNMENT, member_id: "42" })).success
    ).toBe(false)
  })
})

describe("parsePaymentForm", () => {
  it("treats an empty date as 'today', not as an error", () => {
    const result = parsePaymentForm(form({ paid_at: "", payment_method: "" }))
    expect(result.success).toBe(true)
    if (result.success) {
      expect(result.data.paid_at).toBeNull()
      expect(result.data.payment_method).toBeNull()
    }
  })

  it("rejects a malformed date", () => {
    expect(parsePaymentForm(form({ paid_at: "01.02.2026" })).success).toBe(false)
  })
})

describe("sepaExportQuerySchema", () => {
  it("accepts a plain year", () => {
    const result = sepaExportQuerySchema.safeParse({
      year: "2026",
      collection_date: "",
    })
    expect(result.success).toBe(true)
    if (result.success) expect(result.data.year).toBe(2026)
  })

  it("rejects years outside the backend's range and non-years", () => {
    for (const year of ["", "26", "1999", "20260", "zwei"]) {
      expect(
        sepaExportQuerySchema.safeParse({ year, collection_date: "" }).success
      ).toBe(false)
    }
  })

  it("rejects a malformed collection date", () => {
    expect(
      sepaExportQuerySchema.safeParse({
        year: "2026",
        collection_date: "next friday",
      }).success
    ).toBe(false)
  })
})
