import { describe, expect, it } from "vitest"

import {
  parseRuleForm,
  rangeBookQuerySchema,
  revokeReasonSchema,
} from "@/lib/shooting-schema"

function ruleForm(overrides: Record<string, string> = {}): FormData {
  const form = new FormData()
  const values: Record<string, string> = {
    rule_key: "dsb-standard",
    label: "18 Termine oder monatlich",
    window_months: "12",
    min_total_days: "18",
    min_distinct_months: "",
    ...overrides,
  }
  for (const [key, value] of Object.entries(values)) form.set(key, value)
  return form
}

describe("parseRuleForm", () => {
  it("accepts a complete rule and turns empty counts into null", () => {
    const result = parseRuleForm(ruleForm())
    expect(result.success).toBe(true)
    if (result.success) {
      expect(result.data.rule_key).toBe("dsb-standard")
      expect(result.data.window_months).toBe(12)
      expect(result.data.min_total_days).toBe(18)
      expect(result.data.min_distinct_months).toBeNull()
    }
  })

  it("requires at least one criterion", () => {
    const result = parseRuleForm(
      ruleForm({ min_total_days: "", min_distinct_months: "" })
    )
    expect(result.success).toBe(false)
  })

  it("accepts the monthly criterion alone", () => {
    const result = parseRuleForm(
      ruleForm({ min_total_days: "", min_distinct_months: "12" })
    )
    expect(result.success).toBe(true)
  })

  it("rejects a key with forbidden characters", () => {
    expect(parseRuleForm(ruleForm({ rule_key: "DSB Standard" })).success).toBe(
      false
    )
  })

  it("rejects a zero-month window", () => {
    expect(parseRuleForm(ruleForm({ window_months: "0" })).success).toBe(false)
  })

  it("rejects fractional counts", () => {
    expect(parseRuleForm(ruleForm({ min_total_days: "1.5" })).success).toBe(
      false
    )
  })
})

describe("revokeReasonSchema", () => {
  it("mirrors the backend: three characters minimum, trimmed", () => {
    expect(revokeReasonSchema.safeParse("  x  ").success).toBe(false)
    expect(revokeReasonSchema.safeParse("Falsche Regel").success).toBe(true)
  })
})

describe("rangeBookQuerySchema", () => {
  it("accepts an ordered ISO date range", () => {
    expect(
      rangeBookQuerySchema.safeParse({ from: "2026-01-01", to: "2026-07-31" })
        .success
    ).toBe(true)
  })

  it("rejects a reversed range and non-dates", () => {
    expect(
      rangeBookQuerySchema.safeParse({ from: "2026-07-31", to: "2026-01-01" })
        .success
    ).toBe(false)
    expect(
      rangeBookQuerySchema.safeParse({ from: "gestern", to: "2026-01-01" })
        .success
    ).toBe(false)
  })
})
