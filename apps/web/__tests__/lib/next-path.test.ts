import { describe, expect, it } from "vitest"

import { safeNextPath } from "@/lib/next-path"

/**
 * `?next=` decides where a signed-in user is sent, so an unchecked value here
 * is an open redirect: a link to our own login page could bounce a user onto
 * an attacker's site with our domain in the referrer.
 */
describe("safeNextPath", () => {
  it("keeps a plain in-app path", () => {
    expect(safeNextPath("/members")).toBe("/members")
  })

  it("keeps the query string", () => {
    expect(safeNextPath("/members?tab=active")).toBe("/members?tab=active")
  })

  it.each([
    ["absolute URL", "https://evil.com"],
    ["protocol-relative", "//evil.com"],
    ["backslash variant", "/\\evil.com"],
    ["leading backslash", "\\/evil.com"],
    ["javascript scheme", "javascript:alert(1)"],
    ["data scheme", "data:text/html,<script>"],
  ])("rejects %s", (_label, value) => {
    expect(safeNextPath(value)).toBeNull()
  })

  it("rejects a target pointing back at the login page", () => {
    // Would bounce between login and itself forever.
    expect(safeNextPath("/login")).toBeNull()
    expect(safeNextPath("/login?next=%2F")).toBeNull()
  })

  it("treats the app home as no target", () => {
    // Redirecting to the default carries no information.
    expect(safeNextPath("/")).toBeNull()
  })

  it.each([null, undefined, ""])("rejects the empty value %s", (value) => {
    expect(safeNextPath(value)).toBeNull()
  })

  it("strips control characters rather than passing them through", () => {
    // A newline in a Location header is a response-splitting vector.
    expect(safeNextPath("/mem\nbers")).toBe("/members")
  })
})
