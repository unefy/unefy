import { describe, expect, it } from "vitest"

import {
  allSelected,
  pruneSelection,
  toggleAll,
  toggleSelection,
} from "@/lib/library-selection"

const ROWS = [{ id: "a" }, { id: "b" }, { id: "c" }]

describe("pruneSelection", () => {
  it("drops ids that are no longer on screen", () => {
    // The bug this exists for: the page reloads after a delete, and a tick
    // left over from before would send the next bulk action at a document
    // nobody meant to touch.
    expect([...pruneSelection(new Set(["a", "gone"]), ROWS)]).toEqual(["a"])
  })

  it("keeps everything that is still there", () => {
    expect([...pruneSelection(new Set(["a", "c"]), ROWS)].sort()).toEqual([
      "a",
      "c",
    ])
  })

  it("returns a new set rather than editing the old one", () => {
    const selection = new Set(["a", "gone"])
    pruneSelection(selection, ROWS)

    expect(selection.has("gone")).toBe(true)
  })
})

describe("toggleSelection", () => {
  it("ticks and unticks", () => {
    const once = toggleSelection(new Set(), "b")
    expect([...once]).toEqual(["b"])
    expect([...toggleSelection(once, "b")]).toEqual([])
  })
})

describe("toggleAll", () => {
  it("ticks everything when something is missing", () => {
    expect([...toggleAll(new Set(["a"]), ROWS)].sort()).toEqual(["a", "b", "c"])
  })

  it("clears when everything is already ticked", () => {
    expect([...toggleAll(new Set(["a", "b", "c"]), ROWS)]).toEqual([])
  })

  it("does nothing to an empty list", () => {
    expect([...toggleAll(new Set(), [])]).toEqual([])
  })
})

describe("allSelected", () => {
  it("is false for an empty list, so the header box is not ticked", () => {
    expect(allSelected(new Set(), [])).toBe(false)
  })

  it("ignores ticks for rows that are not shown", () => {
    expect(allSelected(new Set(["a", "b", "c", "gone"]), ROWS)).toBe(true)
    expect(allSelected(new Set(["a", "b"]), ROWS)).toBe(false)
  })
})
