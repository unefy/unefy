import { describe, expect, it } from "vitest"

import { parseEventForm } from "@/lib/event-schema"

function form(fields: Record<string, string>): FormData {
  const data = new FormData()
  for (const [key, value] of Object.entries(fields)) data.append(key, value)
  return data
}

const BASE = {
  title: "Übungsabend",
  event_type: "training",
  starts_at: "2026-08-20T17:00:00.000Z",
}

describe("parseEventForm", () => {
  it("accepts the minimum a form can submit", () => {
    const result = parseEventForm(form(BASE))
    expect(result.success).toBe(true)
    if (!result.success) return
    expect(result.data.title).toBe("Übungsabend")
    // Fields the form never rendered must not fail the parse.
    expect(result.data.ends_at).toBeNull()
    expect(result.data.max_participants).toBeNull()
    expect(result.data.registration_required).toBe(false)
  })

  it("turns blank optional fields into null rather than empty strings", () => {
    const result = parseEventForm(
      form({ ...BASE, location: "  ", description: "", ends_at: "" })
    )
    expect(result.success).toBe(true)
    if (!result.success) return
    expect(result.data.location).toBeNull()
    expect(result.data.description).toBeNull()
    expect(result.data.ends_at).toBeNull()
  })

  it("reads the hidden checkbox value both ways", () => {
    const on = parseEventForm(
      form({ ...BASE, all_day: "true", registration_required: "true" })
    )
    expect(on.success && on.data.all_day).toBe(true)
    expect(on.success && on.data.registration_required).toBe(true)

    const off = parseEventForm(
      form({ ...BASE, all_day: "false", registration_required: "false" })
    )
    expect(off.success && off.data.all_day).toBe(false)
    expect(off.success && off.data.registration_required).toBe(false)
  })

  it("rejects an end before the start", () => {
    const result = parseEventForm(
      form({ ...BASE, ends_at: "2026-08-20T16:00:00.000Z" })
    )
    expect(result.success).toBe(false)
  })

  it("accepts an end equal to the start", () => {
    const result = parseEventForm(form({ ...BASE, ends_at: BASE.starts_at }))
    expect(result.success).toBe(true)
  })

  it("rejects a deadline after the event has started", () => {
    const result = parseEventForm(
      form({ ...BASE, registration_deadline: "2026-08-21T17:00:00.000Z" })
    )
    expect(result.success).toBe(false)
  })

  it("rejects a participant limit below one or non-integer", () => {
    expect(parseEventForm(form({ ...BASE, max_participants: "0" })).success).toBe(
      false
    )
    expect(
      parseEventForm(form({ ...BASE, max_participants: "2.5" })).success
    ).toBe(false)
    expect(
      parseEventForm(form({ ...BASE, max_participants: "40" })).success
    ).toBe(true)
  })

  it("rejects an empty title and an unknown type", () => {
    expect(parseEventForm(form({ ...BASE, title: "   " })).success).toBe(false)
    expect(parseEventForm(form({ ...BASE, event_type: "party" })).success).toBe(
      false
    )
  })
})
