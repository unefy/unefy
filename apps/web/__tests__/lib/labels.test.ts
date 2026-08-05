import { describe, expect, it } from "vitest"

import { genderLabel, memberStatusLabel, roleLabel } from "@/lib/labels"

/** Stands in for next-intl's `t`, echoing the key it was asked for. */
const t = (key: string) => `translated:${key}`

describe("label lookup", () => {
  it("translates a known member status", () => {
    expect(memberStatusLabel(t, "resigned")).toBe(
      "translated:memberStatus.resigned"
    )
  })

  it("translates a known role", () => {
    expect(roleLabel(t, "owner")).toBe("translated:roles.owner")
  })

  it("translates a known gender", () => {
    expect(genderLabel(t, "diverse")).toBe("translated:gender.diverse")
  })

  it.each([
    ["member status", memberStatusLabel],
    ["role", roleLabel],
    ["gender", genderLabel],
  ])("falls back to the raw key for an unknown %s", (_label, resolve) => {
    /**
     * The backend may add a value before the translation exists. Showing the
     * raw key is visibly wrong; asking next-intl for a missing key would throw
     * and take the whole table down.
     */
    expect(resolve(t, "brand-new-value")).toBe("brand-new-value")
  })

  it("does not treat an empty value as known", () => {
    expect(memberStatusLabel(t, "")).toBe("")
  })
})
