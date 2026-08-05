"use client"

import { useEffect, useRef, useState, useSyncExternalStore } from "react"
import { createPortal } from "react-dom"

import { cn } from "@/lib/utils"

const noopSubscribe = () => () => {}

/** The topbar's title slot — null during SSR, stable once mounted. */
function useHeaderSlot() {
  return useSyncExternalStore(
    noopSubscribe,
    () => document.getElementById("header-page-title"),
    () => null
  )
}

/**
 * Shows `title` inside the app topbar once the page's own heading has
 * scrolled out from under it — the web counterpart of the Android detail
 * scaffold's collapsing title, and never the same name twice on one screen.
 *
 * Render it directly next to the heading it stands in for: the invisible
 * sentinel marks that spot, and an IntersectionObserver (offset by the
 * topbar's height) reports when it leaves. The title itself is portaled into
 * the `#header-page-title` slot the topbar provides.
 */
export function HeaderScrollTitle({ title }: { title: string }) {
  const sentinelRef = useRef<HTMLSpanElement>(null)
  const slot = useHeaderSlot()
  const [collapsed, setCollapsed] = useState(false)

  useEffect(() => {
    // Same document-scroll listener the topbar itself uses for its shadow —
    // the one scroll mechanism proven to work in this shell.
    const onScroll = () => {
      const sentinel = sentinelRef.current
      if (!sentinel) return
      // The topbar is h-16 (64px): the heading counts as "gone" once its
      // whole line is underneath the bar, not once it leaves the viewport.
      setCollapsed(sentinel.getBoundingClientRect().bottom < 64)
    }
    onScroll()
    document.addEventListener("scroll", onScroll, { passive: true })
    return () => document.removeEventListener("scroll", onScroll)
  }, [])

  return (
    <>
      {/* Zero-width but full line height (self-stretch): the title counts as
          gone when its whole line is under the bar, not when its midpoint is. */}
      <span ref={sentinelRef} aria-hidden className="self-stretch" />
      {slot &&
        createPortal(
          <span
            aria-hidden={!collapsed}
            className={cn(
              "truncate text-sm font-semibold transition-opacity duration-200",
              collapsed ? "opacity-100" : "opacity-0"
            )}
          >
            {title}
          </span>,
          slot
        )}
    </>
  )
}
