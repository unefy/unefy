"use client"

import { useRef, useState } from "react"
import { useTranslations } from "next-intl"

import { Button } from "@/components/ui/button"
import {
  midpoint,
  penWidth,
  velocityBetween,
  type Point,
} from "@/lib/signature"

/**
 * Somewhere to sign with a finger.
 *
 * Pointer events rather than touch events: one code path covers finger, pen
 * and mouse, and the chair signing on a tablet and the treasurer trying it
 * with a trackpad get the same thing.
 *
 * The line is drawn as curves between the midpoints of consecutive samples,
 * with the sample itself as the control point, and its width follows the
 * speed of the stroke. Straight segments of one thickness looked like cable,
 * which is not what a signature looks like. The arithmetic for both lives in
 * `lib/signature`, where it can be tested.
 *
 * The canvas is sized in device pixels and scaled by CSS, otherwise a
 * signature drawn on a phone arrives as a blurred enlargement. What leaves
 * here is a PNG with a transparent background, cropped to the ink — a
 * rectangle of empty pixels would print as a grey box on the certificate.
 */

//: Ink, and a constant rather than a theme colour: what is drawn here goes
//: onto a white PDF page, so it has to be dark whatever the app is wearing.
const INK = "#111111"
//: How thin and how thick the pen gets, in CSS pixels. The spread is what
//: makes the line read as ink rather than as a marker.
const PEN = { min: 1.4, max: 3.6 }
const EXPORT_PADDING = 8

export function SignaturePad({
  onChange,
  disabled = false,
}: {
  onChange: (png: string | null) => void
  disabled?: boolean
}) {
  const t = useTranslations("sign")
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const drawing = useRef(false)
  // The pen's state between samples: where it was, where the last curve
  // ended, how wide it was and when it last moved.
  const last = useRef<Point | null>(null)
  const lastMid = useRef<Point | null>(null)
  const width = useRef(PEN.max)
  const lastAt = useRef(0)
  // The ink's bounding box, so the export can be cropped to it.
  const bounds = useRef<{
    minX: number
    minY: number
    maxX: number
    maxY: number
  } | null>(null)
  const [hasInk, setHasInk] = useState(false)

  function context(): CanvasRenderingContext2D | null {
    const canvas = canvasRef.current
    if (!canvas) return null
    const ratio = window.devicePixelRatio || 1
    if (canvas.width !== Math.round(canvas.clientWidth * ratio)) {
      canvas.width = Math.round(canvas.clientWidth * ratio)
      canvas.height = Math.round(canvas.clientHeight * ratio)
    }
    const ctx = canvas.getContext("2d")
    if (!ctx) return null
    ctx.lineCap = "round"
    ctx.lineJoin = "round"
    ctx.strokeStyle = INK
    return ctx
  }

  function pointOf(event: { clientX: number; clientY: number }): Point {
    const canvas = canvasRef.current
    if (!canvas) return { x: 0, y: 0 }
    const rect = canvas.getBoundingClientRect()
    const ratio = window.devicePixelRatio || 1
    return {
      x: (event.clientX - rect.left) * ratio,
      y: (event.clientY - rect.top) * ratio,
    }
  }

  function start(event: React.PointerEvent<HTMLCanvasElement>) {
    if (disabled) return
    const ctx = context()
    if (!ctx) return
    // Capture, so a finger sliding off the edge finishes its stroke here
    // instead of leaving the pad in a half-drawn state.
    event.currentTarget.setPointerCapture(event.pointerId)
    drawing.current = true

    const point = pointOf(event)
    last.current = point
    lastMid.current = point
    width.current = PEN.max
    lastAt.current = event.timeStamp
    track(point)

    // A tap is a dot, not nothing: somebody who signs with a single stab
    // should see something.
    const ratio = window.devicePixelRatio || 1
    ctx.beginPath()
    ctx.arc(point.x, point.y, (PEN.max * ratio) / 2, 0, Math.PI * 2)
    ctx.fillStyle = INK
    ctx.fill()
    setHasInk(true)
  }

  function move(event: React.PointerEvent<HTMLCanvasElement>) {
    if (!drawing.current) return
    const ctx = context()
    if (!ctx) return

    // Every position the browser batched into this frame, not just the last
    // one. On a phone that is the difference between four samples a stroke
    // and forty — and it is where the smoothness actually comes from.
    const native = event.nativeEvent
    const samples =
      typeof native.getCoalescedEvents === "function"
        ? native.getCoalescedEvents()
        : [native]

    for (const sample of samples.length > 0 ? samples : [native]) {
      draw(ctx, pointOf(sample), sample.timeStamp || event.timeStamp)
    }
  }

  function draw(ctx: CanvasRenderingContext2D, point: Point, at: number) {
    const previous = last.current
    const previousMid = lastMid.current
    if (!previous || !previousMid) return

    const ratio = window.devicePixelRatio || 1
    const velocity = velocityBetween(previous, point, at - lastAt.current)
    width.current = penWidth(velocity, width.current, PEN)

    const mid = midpoint(previous, point)
    ctx.lineWidth = width.current * ratio
    ctx.beginPath()
    ctx.moveTo(previousMid.x, previousMid.y)
    // The sample steers the curve; the segment runs midpoint to midpoint.
    ctx.quadraticCurveTo(previous.x, previous.y, mid.x, mid.y)
    ctx.stroke()

    last.current = point
    lastMid.current = mid
    lastAt.current = at
    track(point)
  }

  function end() {
    if (!drawing.current) return
    drawing.current = false
    last.current = null
    lastMid.current = null
    onChange(exportPng())
  }

  function track(point: Point) {
    const current = bounds.current
    bounds.current = current
      ? {
          minX: Math.min(current.minX, point.x),
          minY: Math.min(current.minY, point.y),
          maxX: Math.max(current.maxX, point.x),
          maxY: Math.max(current.maxY, point.y),
        }
      : { minX: point.x, minY: point.y, maxX: point.x, maxY: point.y }
  }

  function exportPng(): string | null {
    const canvas = canvasRef.current
    const box = bounds.current
    if (!canvas || !box) return null

    // Padded by the widest the pen gets, so a stroke is never clipped at its
    // own edge.
    const pad = EXPORT_PADDING + PEN.max
    const left = Math.max(0, box.minX - pad)
    const top = Math.max(0, box.minY - pad)
    const width = Math.min(canvas.width - left, box.maxX - box.minX + pad * 2)
    const height = Math.min(canvas.height - top, box.maxY - box.minY + pad * 2)

    const cropped = document.createElement("canvas")
    cropped.width = Math.max(1, Math.ceil(width))
    cropped.height = Math.max(1, Math.ceil(height))
    const ctx = cropped.getContext("2d")
    if (!ctx) return null
    ctx.drawImage(
      canvas,
      left,
      top,
      cropped.width,
      cropped.height,
      0,
      0,
      cropped.width,
      cropped.height
    )
    return cropped.toDataURL("image/png")
  }

  function clear() {
    const canvas = canvasRef.current
    const ctx = canvas?.getContext("2d")
    if (canvas && ctx) ctx.clearRect(0, 0, canvas.width, canvas.height)
    bounds.current = null
    last.current = null
    lastMid.current = null
    setHasInk(false)
    onChange(null)
  }

  return (
    <div className="space-y-2">
      <canvas
        ref={canvasRef}
        // `touch-none`, or the browser scrolls the page instead of drawing.
        //
        // White in both themes, and the ink dark to match: the pad is a piece
        // of paper, not a part of the interface — in dark mode a themed
        // background left the strokes black on near-black, and the drawing
        // ends up on a white page either way.
        //
        // Taller where the pointer is a finger. Sized by pointer rather than
        // by viewport: a tablet in landscape is a wide screen and still wants
        // room to sign.
        className="h-48 w-full touch-none rounded-lg border border-input bg-white pointer-coarse:h-72"
        onPointerDown={start}
        onPointerMove={move}
        onPointerUp={end}
        onPointerCancel={end}
        aria-label={t("padLabel")}
      />
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">{t("padHint")}</p>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={clear}
          disabled={disabled || !hasInk}
        >
          {t("clear")}
        </Button>
      </div>
    </div>
  )
}
