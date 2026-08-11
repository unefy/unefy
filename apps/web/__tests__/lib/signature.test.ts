import { describe, expect, it } from "vitest"

import {
  distance,
  localPoint,
  midpoint,
  penRange,
  penWidth,
  velocityBetween,
} from "@/lib/signature"

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

describe("penRange", () => {
  it("grows with the pad, so a bigger pad is not a fainter signature", () => {
    // The drawing is squeezed to a fixed height on the page. A pen of fixed
    // width would come out of a full-screen pad thinner than out of a small
    // one, which is the complaint this exists to answer.
    const small = penRange(200)
    const large = penRange(400)

    expect(large.max).toBeGreaterThan(small.max)
    expect(large.max / large.min).toBeCloseTo(small.max / small.min, 5)
  })

  it("keeps a usable pen on a pad small enough to hit the floor", () => {
    const tiny = penRange(20)

    expect(tiny.min).toBeGreaterThanOrEqual(1.6)
    expect(tiny.max).toBeGreaterThan(tiny.min)
  })

  it("stops growing once the pad is taller than anybody signs", () => {
    // A pad the height of a phone held upright is mostly empty space; a pen
    // that kept scaling with it would draw a marker.
    expect(penRange(900).max).toEqual(penRange(400).max)
    expect(penRange(900).max).toBeLessThan(11)
  })

  it("leaves room to taper at every size", () => {
    for (const height of [80, 192, 288, 430, 900]) {
      const range = penRange(height)
      expect(range.max).toBeGreaterThan(range.min)
    }
  })
})

describe("localPoint", () => {
  const rect = { left: 10, top: 20, right: 110 }

  it("subtracts the pad's corner when the pad stands upright", () => {
    expect(localPoint({ x: 40, y: 50 }, rect, false)).toEqual({ x: 30, y: 30 })
  })

  it("swaps the axes when the pad is turned a quarter turn", () => {
    // Turned clockwise, the pad's own x runs down the screen and its y runs
    // to the left: without this the ink would appear at right angles to the
    // finger that drew it.
    expect(localPoint({ x: 40, y: 50 }, rect, true)).toEqual({ x: 30, y: 70 })
  })

  it("puts the turned pad's origin at the screen's top right", () => {
    expect(localPoint({ x: rect.right, y: rect.top }, rect, true)).toEqual({
      x: 0,
      y: 0,
    })
  })
})
