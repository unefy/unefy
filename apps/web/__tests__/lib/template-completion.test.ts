import { describe, expect, it } from "vitest"

import { completeAt, openPlaceholder } from "@/lib/template-completion"

describe("openPlaceholder", () => {
  it("offers the list as soon as the braces are open", () => {
    // "" and null are different answers: an open placeholder with nothing
    // typed should show every variable, not no list at all.
    expect(openPlaceholder("Hallo {{", 8)).toBe("")
  })

  it("returns what has been typed into it", () => {
    expect(openPlaceholder("Hallo {{mitglied", 16)).toBe("mitglied")
  })

  it("stops once the placeholder is closed", () => {
    /**
     * Otherwise the list would reappear behind every finished placeholder and
     * the next keystroke would land in a completion nobody asked for.
     */
    expect(openPlaceholder("{{datum}} und dann", 18)).toBeNull()
  })

  it("stops at a line break", () => {
    // A stray "{{" two paragraphs up is a typo, not an open completion.
    expect(openPlaceholder("{{ oops\nnächste Zeile", 21)).toBeNull()
  })

  it("is null where there are no braces at all", () => {
    expect(openPlaceholder("ganz normaler Text", 10)).toBeNull()
  })

  it("looks only at the text before the caret", () => {
    // The caret sits before the braces, so nothing is being completed.
    expect(openPlaceholder("Hallo {{datum}}", 3)).toBeNull()
  })

  it("uses the nearest opening braces", () => {
    expect(openPlaceholder("{{datum}} {{mit", 15)).toBe("mit")
  })
})

describe("completeAt", () => {
  it("replaces the open braces and puts the caret behind them", () => {
    const result = completeAt("Hallo {{mit", 11, "mitglied.name")

    expect(result?.text).toBe("Hallo {{mitglied.name}}")
    expect(result?.caret).toBe(23)
  })

  it("keeps what follows the caret", () => {
    const result = completeAt("Hallo {{mit, guten Tag", 11, "mitglied.name")

    expect(result?.text).toBe("Hallo {{mitglied.name}}, guten Tag")
  })

  it("inserts into a bare pair of braces", () => {
    const result = completeAt("{{", 2, "datum")

    expect(result?.text).toBe("{{datum}}")
    expect(result?.caret).toBe(9)
  })

  it("does nothing without an opening", () => {
    expect(completeAt("kein Platzhalter", 5, "datum")).toBeNull()
  })
})
