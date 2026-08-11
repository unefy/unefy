import { describe, expect, it } from "vitest"

import { distance, midpoint, penWidth, velocityBetween } from "@/lib/signature"

const RANGE = { min: 1.2, max: 3.6 }

describe("midpoint", () => {
  it("sits halfway between the two samples", () => {
    expect(midpoint({ x: 0, y: 0 }, { x: 10, y: 4 })).toEqual({ x: 5, y: 2 })
  })

  it("is the same point when both samples are", () => {
    expect(midpoint({ x: 3, y: 7 }, { x: 3, y: 7 })).toEqual({ x: 3, y: 7 })
  })
})

describe("penWidth", () => {
  it("is thinner the faster the stroke is drawn", () => {
    const slow = penWidth(0.1, RANGE.max, RANGE)
    const fast = penWidth(3, RANGE.max, RANGE)

    expect(fast).toBeLessThan(slow)
  })

  it("stays inside the range whatever the speed", () => {
    for (const velocity of [0, 0.5, 1, 5, 50]) {
      const width = penWidth(velocity, RANGE.min, RANGE)
      expect(width).toBeGreaterThanOrEqual(RANGE.min)
      expect(width).toBeLessThanOrEqual(RANGE.max)
    }
  })

  it("moves towards the new width rather than jumping to it", () => {
    // A single fast sample in the middle of a slow stroke must not put a knot
    // in the line: the pen narrows towards it over the next few samples.
    const width = penWidth(3, RANGE.max, RANGE)

    expect(width).toBeGreaterThan(RANGE.min)
    expect(width).toBeLessThan(RANGE.max)
  })
})

describe("velocityBetween", () => {
  it("is distance over time", () => {
    expect(velocityBetween({ x: 0, y: 0 }, { x: 30, y: 40 }, 10)).toBe(5)
  })

  it("survives two samples carrying the same timestamp", () => {
    // Coalesced events do arrive with an identical timestamp; dividing by that
    // gap would hand the pen an infinite velocity and a width of NaN.
    const velocity = velocityBetween({ x: 0, y: 0 }, { x: 4, y: 0 }, 0)

    expect(Number.isFinite(velocity)).toBe(true)
    expect(Number.isFinite(penWidth(velocity, RANGE.max, RANGE))).toBe(true)
  })
})

describe("distance", () => {
  it("is the straight line between two points", () => {
    expect(distance({ x: 0, y: 0 }, { x: 3, y: 4 })).toBe(5)
  })
})
