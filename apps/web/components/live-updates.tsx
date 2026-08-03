"use client"

import { usePathname } from "next/navigation"

import { useLiveUpdates } from "@/hooks/use-live-updates"

/**
 * Which change hints each route actually displays. A page only re-renders for
 * entities it shows: on a busy check-in evening, someone reading the settings
 * must not have every server component re-run for each member edit elsewhere.
 *
 * First matching prefix wins. Routes not listed refresh on every hint — the
 * safe default for a page whose data needs are unknown here. When a new page
 * starts displaying a synced collection, add its prefix.
 */
const ROUTE_COLLECTIONS: ReadonlyArray<
  readonly [prefix: string, collections: readonly string[]]
> = [["/members", ["members"]]]

/**
 * Mounts the change stream for the whole signed-in shell.
 *
 * Placed in the `(app)` layout rather than on individual pages, for two reasons.
 * The layout does not remount across navigation, so one connection serves the
 * whole session instead of being torn down and re-opened on every route change —
 * which matters, because the backend caps concurrent streams per user. And every
 * page under it is a Server Component reading through Server Actions, so
 * `router.refresh()` is the right and only lever regardless of which page is open.
 * The hook keeps the connection across route changes; only the filter follows
 * the route.
 *
 * Renders nothing.
 */
export function LiveUpdates() {
  const pathname = usePathname()
  const match = ROUTE_COLLECTIONS.find(([prefix]) => pathname.startsWith(prefix))
  useLiveUpdates(match ? { collections: match[1] } : undefined)
  return null
}
