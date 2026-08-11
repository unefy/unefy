"use client"

import { useRef, useState } from "react"
import { useTranslations } from "next-intl"

import { Button } from "@/components/ui/button"
import {
  localPoint,
  midpoint,
  penRange,
  penWidth,
  velocityBetween,
  type PenRange,
  type Point,
} from "@/lib/signature"
import { cn } from "@/lib/utils"

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
 * Everything here is measured in CSS pixels and the canvas is scaled once, to
 * device pixels, on the way out. Working in device pixels made the pen behave
 * differently on every screen — the same movement on a phone counts three
 * times the speed of the same movement on a plain monitor, so a phone drew
 * everything at the thin end of the range. What leaves here is a PNG with a
 * transparent background, cropped to the ink: a rectangle of empty pixels
 * would print as a grey box on the certificate.
 */

//: Ink, and a constant rather than a theme colour: what is drawn here goes
//: onto a white PDF page, so it has to be dark whatever the app is wearing.
const INK = "#111111"
const EXPORT_PADDING = 8
//: The exported drawing is squeezed to 16mm on the page, so beyond this it is
//: only bytes. A full-screen pad on a modern phone is some 2500 device pixels
//: across, and the signature has to survive an upload limit.
const MAX_EXPORT_EDGE = 1400

export function SignaturePad({
  onChange,
  disabled = false,
  fill = false,
  quarterTurn = false,
}: {
  onChange: (png: string | null) => void
  disabled?: boolean
  /** Fill the parent instead of standing at a fixed height. */
  fill?: boolean
  /** The surface is turned a quarter turn clockwise by its container. */
  quarterTurn?: boolean
}) {
  const t = useTranslations("sign")
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const drawing = useRef(false)
  // The pen's state between samples: where it was, where the last curve
  // ended, how wide it was, when it last moved and how wide it may get.
  const last = useRef<Point | null>(null)
  const lastMid = useRef<Point | null>(null)
  const width = useRef(0)
  const lastAt = useRef(0)
  const pen = useRef<PenRange>(penRange(0))
  // The ink's bounding box in CSS pixels, so the export can be cropped to it.
  const bounds = useRef<{
    minX: number
    minY: number
    maxX: number
    maxY: number
  } | null>(null)
  const [hasInk, setHasInk] = useState(false)

  function ratioOf(): number {
    return window.devicePixelRatio || 1
  }

  function context(): CanvasRenderingContext2D | null {
    const canvas = canvasRef.current
    if (!canvas) return null
    const ratio = ratioOf()
    const wantedWidth = Math.round(canvas.clientWidth * ratio)
    const wantedHeight = Math.round(canvas.clientHeight * ratio)
    // Resizing a canvas wipes it, so only when the size really changed — a
    // phone turned, a window dragged.
    if (canvas.width !== wantedWidth || canvas.height !== wantedHeight) {
      canvas.width = wantedWidth
      canvas.height = wantedHeight
    }
    const ctx = canvas.getContext("2d")
    if (!ctx) return null
    // One scale for the whole surface, so everything below is CSS pixels.
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0)
    ctx.lineCap = "round"
    ctx.lineJoin = "round"
    ctx.strokeStyle = INK
    return ctx
  }

  function pointOf(event: { clientX: number; clientY: number }): Point {
    const canvas = canvasRef.current
    if (!canvas) return { x: 0, y: 0 }
    const rect = canvas.getBoundingClientRect()
    return localPoint({ x: event.clientX, y: event.clientY }, rect, quarterTurn)
  }

  function start(event: React.PointerEvent<HTMLCanvasElement>) {
    if (disabled) return
    const ctx = context()
    const canvas = canvasRef.current
    if (!ctx || !canvas) return
    // Capture, so a finger sliding off the edge finishes its stroke here
    // instead of leaving the pad in a half-drawn state.
    event.currentTarget.setPointerCapture(event.pointerId)
    drawing.current = true

    // The pad can change size between strokes — a phone turned, a window
    // dragged — and the pen is sized against it.
    pen.current = penRange(canvas.clientHeight)

    const point = pointOf(event)
    last.current = point
    lastMid.current = point
    // Start in the middle of the range. Starting at the widest put a blob on
    // the beginning of every stroke, because a hand is already moving by the
    // time the second sample arrives and the pen then narrows away from it.
    width.current = (pen.current.min + pen.current.max) / 2
    lastAt.current = event.timeStamp
    track(point)

    // A tap is a dot, not nothing: somebody who signs with a single stab
    // should see something. As thick as the thinnest stroke, so it reads as
    // part of the writing rather than as a spot of spilled ink.
    ctx.beginPath()
    ctx.arc(point.x, point.y, pen.current.min / 2, 0, Math.PI * 2)
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

    const velocity = velocityBetween(previous, point, at - lastAt.current)
    width.current = penWidth(velocity, width.current, pen.current)

    const mid = midpoint(previous, point)
    ctx.lineWidth = width.current
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
    // own edge. Still in CSS pixels; device pixels come at the crop.
    const ratio = ratioOf()
    const pad = EXPORT_PADDING + pen.current.max
    const left = Math.max(0, box.minX - pad) * ratio
    const top = Math.max(0, box.minY - pad) * ratio
    const cropWidth = Math.min(
      canvas.width - left,
      (box.maxX - box.minX + pad * 2) * ratio
    )
    const cropHeight = Math.min(
      canvas.height - top,
      (box.maxY - box.minY + pad * 2) * ratio
    )
    if (cropWidth <= 0 || cropHeight <= 0) return null

    const scale = Math.min(1, MAX_EXPORT_EDGE / Math.max(cropWidth, cropHeight))
    const cropped = document.createElement("canvas")
    cropped.width = Math.max(1, Math.round(cropWidth * scale))
    cropped.height = Math.max(1, Math.round(cropHeight * scale))
    const ctx = cropped.getContext("2d")
    if (!ctx) return null
    ctx.imageSmoothingQuality = "high"
    ctx.drawImage(
      canvas,
      left,
      top,
      cropWidth,
      cropHeight,
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
    if (canvas && ctx) {
      ctx.setTransform(1, 0, 0, 1, 0, 0)
      ctx.clearRect(0, 0, canvas.width, canvas.height)
    }
    bounds.current = null
    last.current = null
    lastMid.current = null
    setHasInk(false)
    onChange(null)
  }

  return (
    <div
      className={cn("flex flex-col gap-2", fill ? "min-h-0 flex-1" : undefined)}
    >
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
        className={cn(
          "w-full touch-none rounded-lg border border-input bg-white",
          fill ? "min-h-0 flex-1" : "h-48 pointer-coarse:h-72"
        )}
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
