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

/** How wide the pen is allowed to get, in CSS pixels. */
export type PenRange = { min: number; max: number }

//: How wide the pen is, as a share of the pad's height. A share rather than a
//: number of pixels because the drawing is scaled to a fixed height on the
//: page: a signature drawn on a full screen is shrunk far more than one drawn
//: in a small box, and a pen of fixed width would print thinner for it.
const PEN_MIN_SHARE = 0.01
const PEN_MAX_SHARE = 0.024
//: Below this the line stops reading as ink whatever the pad's size.
const PEN_FLOOR = 1.6
//: Past this height nobody signs any bigger — they sign their usual size in
//: the middle of the space and leave the rest empty. Scaling the pen with a
//: pad that tall would draw a marker.
const PEN_REFERENCE_CEILING = 400

/**
 * How wide the pen should be on a pad of this height.
 *
 * The width is tied to the pad so that the same hand movement leaves the same
 * mark on the finished document, whether it was drawn in a dialog on a laptop
 * or across the whole of a phone held sideways.
 */
export function penRange(padHeight: number): PenRange {
  const reference = Math.min(padHeight, PEN_REFERENCE_CEILING)
  const min = Math.max(reference * PEN_MIN_SHARE, PEN_FLOOR)
  // The spread is what lets the stroke taper; keep it even on a pad small
  // enough that the floor has taken over the lower end.
  return { min, max: Math.max(reference * PEN_MAX_SHARE, min * 2) }
}

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

/** The part of a DOMRect this file needs. */
export type Rect = { left: number; top: number; right: number }

/**
 * Where a pointer landed, in the pad's own coordinates.
 *
 * A phone that will not turn — rotation lock is on more often than not — gets
 * the signing surface turned a quarter turn clockwise instead, so it can still
 * be signed the long way round. The browser goes on reporting pointers in
 * screen coordinates, and a bounding rectangle of a rotated element is its
 * upright box, so the usual `clientX - left` would put the ink at right angles
 * to the finger. Turning the surface clockwise means the pad's x runs down the
 * screen and its y runs to the left.
 */
export function localPoint(
  client: Point,
  rect: Rect,
  quarterTurn: boolean
): Point {
  if (!quarterTurn) {
    return { x: client.x - rect.left, y: client.y - rect.top }
  }
  return { x: client.y - rect.top, y: rect.right - client.x }
}
