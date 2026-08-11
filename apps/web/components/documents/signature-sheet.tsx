"use client"

import { useEffect, useRef, useState } from "react"
import { useTranslations } from "next-intl"

import {
  SignaturePad,
  type SignaturePadHandle,
} from "@/components/documents/signature-pad"
import { Button } from "@/components/ui/button"
import { EraserIcon } from "lucide-react"

/**
 * The whole screen, turned sideways, to sign on.
 *
 * A signature is a wide, short thing, and a phone held upright is the exact
 * opposite. So the signing surface takes the entire screen and, while the
 * viewport is upright, turns itself a quarter turn: the pad then runs along
 * the long side of the phone and the person signs the way they would on
 * paper.
 *
 * Turning our own surface rather than asking the phone to turn, because the
 * phone usually will not. Safari on iOS has no orientation lock API at all,
 * and on any device the owner's own rotation lock overrules the page. Whoever
 * has rotation switched off simply turns the phone and the surface is already
 * upright for them; whoever has it on gets the same picture without turning
 * anything, because the media query never fires. Both end up signing the long
 * way round.
 */

/** Whether the surface should turn itself: an upright screen held in a hand. */
function useUpright(): boolean {
  const [upright, setUpright] = useState(false)

  useEffect(() => {
    // Coarse as well as upright: a browser window on a desk that happens to
    // be taller than it is wide has plenty of room and no reason to turn.
    const query = window.matchMedia(
      "(orientation: portrait) and (pointer: coarse)"
    )
    const update = () => setUpright(query.matches)
    update()
    query.addEventListener("change", update)
    return () => query.removeEventListener("change", update)
  }, [])

  return upright
}

export function SignatureSheet({
  confirmLabel,
  pending = false,
  onConfirm,
  onCancel,
}: {
  confirmLabel: string
  pending?: boolean
  onConfirm: (png: string) => void
  onCancel: () => void
}) {
  const t = useTranslations("sign")
  const upright = useUpright()
  const pad = useRef<SignaturePadHandle>(null)
  const [signature, setSignature] = useState<string | null>(null)

  // Nothing behind this should scroll while a finger is drawing on it.
  useEffect(() => {
    const previous = document.body.style.overflow
    document.body.style.overflow = "hidden"
    return () => {
      document.body.style.overflow = previous
    }
  }, [])

  return (
    <div className="fixed inset-0 z-50 overscroll-none bg-white">
      <div
        className="absolute top-0 left-0 flex flex-col gap-3 p-3"
        style={
          upright
            ? {
                // As wide as the screen is tall and the other way about, then
                // turned clockwise about its top left corner and pushed back
                // down into place. The result covers the viewport exactly.
                width: "100dvh",
                height: "100dvw",
                transformOrigin: "top left",
                transform: "rotate(90deg) translateY(-100%)",
              }
            : { width: "100%", height: "100%" }
        }
      >
        <SignaturePad
          fill
          ref={pad}
          quarterTurn={upright}
          onChange={setSignature}
          disabled={pending}
        />
        {/* Starting over belongs next to signing, at the same weight. Nobody
            gets their signature right first time, and a small grey button in
            a corner is not an answer to that. */}
        <div className="flex shrink-0 items-center justify-between gap-2">
          <Button
            type="button"
            variant="ghost"
            onClick={onCancel}
            disabled={pending}
          >
            {t("cancel")}
          </Button>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => pad.current?.clear()}
              disabled={pending || signature === null}
            >
              <EraserIcon />
              {t("clear")}
            </Button>
            <Button
              type="button"
              onClick={() => signature && onConfirm(signature)}
              disabled={pending || signature === null}
            >
              {pending ? t("submitting") : confirmLabel}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
