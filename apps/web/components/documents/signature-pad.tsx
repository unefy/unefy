"use client"

import { useRef, useState } from "react"
import { useTranslations } from "next-intl"

import { Button } from "@/components/ui/button"

/**
 * Somewhere to sign with a finger.
 *
 * Pointer events rather than touch events: one code path covers finger, pen
 * and mouse, and the chair signing on a tablet and the treasurer trying it
 * with a trackpad get the same thing.
 *
 * The canvas is sized in device pixels and scaled by CSS, otherwise a
 * signature drawn on a phone arrives as a blurred enlargement. What leaves
 * here is a PNG with a transparent background, cropped to the ink — a
 * rectangle of empty pixels would print as a grey box on the certificate.
 */

//: Ink, and it is a constant rather than a theme colour: what is drawn here
//: goes onto a white PDF page, so it has to be dark whatever the app is
//: wearing.
const INK = "#111111"
//: Wide enough that a fingertip leaves a line somebody can read on paper.
const PEN_WIDTH = 3
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
    if (canvas.width !== canvas.clientWidth * ratio) {
      canvas.width = canvas.clientWidth * ratio
      canvas.height = canvas.clientHeight * ratio
    }
    const ctx = canvas.getContext("2d")
    if (!ctx) return null
    ctx.lineCap = "round"
    ctx.lineJoin = "round"
    ctx.strokeStyle = INK
    ctx.lineWidth = PEN_WIDTH * ratio
    return ctx
  }

  function pointOf(event: React.PointerEvent<HTMLCanvasElement>) {
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
    const { x, y } = pointOf(event)
    ctx.beginPath()
    ctx.moveTo(x, y)
    track(x, y)
  }

  function move(event: React.PointerEvent<HTMLCanvasElement>) {
    if (!drawing.current) return
    const ctx = context()
    if (!ctx) return
    const { x, y } = pointOf(event)
    ctx.lineTo(x, y)
    ctx.stroke()
    track(x, y)
    if (!hasInk) setHasInk(true)
  }

  function end() {
    if (!drawing.current) return
    drawing.current = false
    onChange(exportPng())
  }

  function track(x: number, y: number) {
    const current = bounds.current
    bounds.current = current
      ? {
          minX: Math.min(current.minX, x),
          minY: Math.min(current.minY, y),
          maxX: Math.max(current.maxX, x),
          maxY: Math.max(current.maxY, y),
        }
      : { minX: x, minY: y, maxX: x, maxY: y }
  }

  function exportPng(): string | null {
    const canvas = canvasRef.current
    const box = bounds.current
    if (!canvas || !box) return null

    const pad = EXPORT_PADDING
    const width = Math.max(1, Math.ceil(box.maxX - box.minX) + pad * 2)
    const height = Math.max(1, Math.ceil(box.maxY - box.minY) + pad * 2)
    const cropped = document.createElement("canvas")
    cropped.width = width
    cropped.height = height
    const ctx = cropped.getContext("2d")
    if (!ctx) return null
    ctx.drawImage(
      canvas,
      Math.max(0, box.minX - pad),
      Math.max(0, box.minY - pad),
      width,
      height,
      0,
      0,
      width,
      height
    )
    return cropped.toDataURL("image/png")
  }

  function clear() {
    const canvas = canvasRef.current
    const ctx = canvas?.getContext("2d")
    if (canvas && ctx) ctx.clearRect(0, 0, canvas.width, canvas.height)
    bounds.current = null
    setHasInk(false)
    onChange(null)
  }

  return (
    <div className="space-y-2">
      <canvas
        ref={canvasRef}
        // `touch-none`, or the browser scrolls the page instead of drawing.
        // White in both themes, and the ink dark to match. The pad is a piece
        // of paper, not a part of the interface: in dark mode a themed
        // background left the strokes black on near-black, and the drawing
        // ends up on a white page either way.
        className="h-48 w-full touch-none rounded-lg border border-input bg-white"
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
