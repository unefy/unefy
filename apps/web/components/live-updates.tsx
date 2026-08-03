"use client"

import { useLiveUpdates } from "@/hooks/use-live-updates"

/**
 * Mounts the change stream for the whole signed-in shell.
 *
 * Placed in the `(app)` layout rather than on individual pages, for two reasons.
 * The layout does not remount across navigation, so one connection serves the
 * whole session instead of being torn down and re-opened on every route change —
 * which matters, because the backend caps concurrent streams per user. And every
 * page under it is a Server Component reading through Server Actions, so
 * `router.refresh()` is the right and only lever regardless of which page is open.
 *
 * Renders nothing.
 */
export function LiveUpdates() {
  useLiveUpdates()
  return null
}
