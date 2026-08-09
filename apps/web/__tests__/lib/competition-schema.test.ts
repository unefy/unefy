import { describe, expect, it } from "vitest"

import {
  parseCompetitionForm,
  parseEntryForm,
  parseSessionForm,
} from "@/lib/competition-schema"

function form(fields: Record<string, string>): FormData {
  const data = new FormData()
  for (const [key, value] of Object.entries(fields)) data.append(key, value)
  return data
}

const COMP = {
  name: "Vereinsmeisterschaft",
  competition_type: "competition",
  start_date: "2026-03-01",
  scoring_mode: "highest_wins",
  scoring_unit: "Ringe",
}

describe("parseCompetitionForm", () => {
  it("accepts the minimum a form can submit", () => {
    const result = parseCompetitionForm(form(COMP))
    expect(result.success).toBe(true)
    if (!result.success) return
    expect(result.data.end_date).toBeNull()
    expect(result.data.disciplines).toBeNull()
  })

  it("keeps the unit free text — every sport counts something else", () => {
    for (const unit of ["Punkte", "Ringe", "Sekunden", "Meter", "kg"]) {
      const result = parseCompetitionForm(form({ ...COMP, scoring_unit: unit }))
      expect(result.success).toBe(true)
      if (result.success) expect(result.data.scoring_unit).toBe(unit)
    }
  })

  it("supports lowest-wins scoring, as a running club needs", () => {
    const result = parseCompetitionForm(
      form({ ...COMP, scoring_mode: "lowest_wins", scoring_unit: "Sekunden" })
    )
    expect(result.success).toBe(true)
    if (result.success) expect(result.data.scoring_mode).toBe("lowest_wins")
  })

  it("splits disciplines on commas and drops the gaps", () => {
    const result = parseCompetitionForm(
      form({ ...COMP, disciplines: "Luftgewehr, , KK 50m ,  " })
    )
    expect(result.success).toBe(true)
    if (result.success) {
      expect(result.data.disciplines).toEqual(["Luftgewehr", "KK 50m"])
    }
  })

  it("rejects an end before the start", () => {
    expect(
      parseCompetitionForm(form({ ...COMP, end_date: "2026-02-28" })).success
    ).toBe(false)
  })

  it("rejects an empty unit and an unknown mode", () => {
    expect(
      parseCompetitionForm(form({ ...COMP, scoring_unit: "  " })).success
    ).toBe(false)
    expect(
      parseCompetitionForm(form({ ...COMP, scoring_mode: "draw" })).success
    ).toBe(false)
  })

  it("rejects free_training, which is machinery and not a competition", () => {
    expect(
      parseCompetitionForm(form({ ...COMP, competition_type: "free_training" }))
        .success
    ).toBe(false)
  })
})

describe("parseSessionForm", () => {
  it("accepts a date alone — name and place are optional", () => {
    const result = parseSessionForm(form({ date: "2026-03-07" }))
    expect(result.success).toBe(true)
    if (result.success) {
      expect(result.data.name).toBeNull()
      expect(result.data.location).toBeNull()
    }
  })

  it("rejects a missing or malformed date", () => {
    expect(parseSessionForm(form({})).success).toBe(false)
    expect(parseSessionForm(form({ date: "07.03.2026" })).success).toBe(false)
  })
})

describe("parseEntryForm", () => {
  const MEMBER = "3f6b8f4e-1a2b-4c3d-8e9f-0a1b2c3d4e5f"

  it("accepts a comma as the decimal separator", () => {
    const result = parseEntryForm(
      form({ member_id: MEMBER, score_value: "12,34" })
    )
    expect(result.success).toBe(true)
    if (result.success) expect(result.data.score_value).toBe("12.34")
  })

  it("keeps three decimals, as a timed sport needs", () => {
    const result = parseEntryForm(
      form({ member_id: MEMBER, score_value: "9.581" })
    )
    expect(result.success).toBe(true)
    if (result.success) expect(result.data.score_value).toBe("9.581")
  })

  it("rejects a score that is not a number", () => {
    for (const score of ["", "abc", "-1", "1.2345"]) {
      expect(
        parseEntryForm(form({ member_id: MEMBER, score_value: score })).success
      ).toBe(false)
    }
  })

  it("rejects a non-uuid member", () => {
    expect(
      parseEntryForm(form({ member_id: "someone", score_value: "10" })).success
    ).toBe(false)
  })
})
