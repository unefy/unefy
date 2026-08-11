/**
 * The arithmetic behind a drawn signature.
 *
 * A pointer reports positions a few milliseconds apart, and joining them with
 * straight lines of one width gives what a marker pen gives: visible corners
 * and a stroke of dead-even thickness. Two things fix that, and both are
 * arithmetic rather than drawing, so they live here where they can be checked.
 */

export type Point = { x: number; y: number }

/**
 * The point halfway between two samples.
 *
 * Curves are drawn from midpoint to midpoint with the sample itself as the
 * control point: that is what rounds the corners. Anchoring on the samples
 * instead would put a cusp at every one of them.
 */
export function midpoint(a: Point, b: Point): Point {
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }
}

export function distance(a: Point, b: Point): number {
  return Math.hypot(b.x - a.x, b.y - a.y)
}

/** How wide the pen is allowed to get, in canvas pixels before scaling. */
export type PenRange = { min: number; max: number }

/**
 * How wide the pen should be for a stroke drawn at this speed.
 *
 * Fast means thin, slow means thick — that is how ink behaves, and it is what
 * makes a finger-drawn line read as handwriting rather than as a cable. The
 * result is blended with the previous width so the stroke tapers instead of
 * stepping: one jittery sample must not produce a visible knot.
 */
export function penWidth(
  velocity: number,
  previous: number,
  range: PenRange
): number {
  // Beyond this speed the pen is as thin as it gets. Picked so that a normal
  // signing motion lands inside the range rather than pinned at one end.
  const fastest = 2.2
  const eased = Math.min(velocity / fastest, 1)
  const target = range.max - (range.max - range.min) * eased
  // Two thirds new, one third old: enough to follow a change of pace, not so
  // much that a single stray sample shows. Clamped afterwards because the
  // blend of two values sitting on a bound can land a hair outside it, and a
  // range that is only nearly kept is not a range.
  const blended = previous * 0.33 + target * 0.67
  return Math.min(Math.max(blended, range.min), range.max)
}

/**
 * Speed in pixels per millisecond, guarded against a zero interval.
 *
 * Browsers do coalesce events into one frame, and two samples then carry the
 * same timestamp — dividing by that gap would make the pen infinitely thin.
 */
export function velocityBetween(
  from: Point,
  to: Point,
  elapsedMs: number
): number {
  return distance(from, to) / Math.max(elapsedMs, 1)
}
