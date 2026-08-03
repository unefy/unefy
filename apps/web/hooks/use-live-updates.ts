"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"

/**
 * Keeps the current page current.
 *
 * The whole mechanism is: listen for change hints, then call `router.refresh()`.
 * Server Components re-run, Server Actions stay the only data path, and nothing
 * about how this app fetches data changes. `router.refresh()` is already the
 * invalidation primitive the mutation dialogs use after their own writes
 * (`components/attendance/*.tsx`) — this points the same lever at somebody
 * else's writes.
 *
 * Deliberately not a data channel. The hints carry an entity name and an id and
 * no row content, so there is nothing here to render and nothing to keep in step
 * with the server's idea of a member. See `backend/app/events/outbox.py`.
 */

/** Hints inside this window collapse into one refresh. */
const COALESCE_MS = 250

export function useLiveUpdates(options?: { collections?: readonly string[] }): void {
  const router = useRouter()

  // Keyed on the contents, not the array. Callers pass a literal — `{ collections:
  // ["members"] }` — which is a new object every render, and depending on its
  // identity would tear down and re-open the connection on each one. That is not a
  // subtle inefficiency: reconnect storms are what the backend's per-user stream
  // cap exists to stop, so this page would lock itself out after three renders.
  const key = options?.collections?.join(",") ?? ""

  useEffect(() => {
    const collections = key === "" ? null : key.split(",")

    // A save that touches a member, their dues and an audit row arrives as three
    // hints in as many milliseconds. Refreshing per hint would re-render the tree
    // three times and re-run every server component with it.
    let timer: ReturnType<typeof setTimeout> | null = null
    const schedule = () => {
      if (timer !== null) return
      timer = setTimeout(() => {
        timer = null
        router.refresh()
      }, COALESCE_MS)
    }

    const source = new EventSource("/api/stream")

    source.addEventListener("change", (event) => {
      if (!collections) {
        schedule()
        return
      }
      // Opting a page into only what it displays. A malformed frame is ignored
      // rather than thrown: a refresh too few is a stale page, but an exception
      // in an EventSource handler takes the whole listener down.
      try {
        const hint = JSON.parse((event as MessageEvent<string>).data) as {
          entity?: string
        }
        if (hint.entity && collections.includes(hint.entity)) schedule()
      } catch {
        schedule()
      }
    })

    // No onerror handler that closes the source: EventSource reconnects on its
    // own with backoff, and closing it here would turn a backend restart into a
    // page that stays stale until the user reloads.

    return () => {
      if (timer !== null) clearTimeout(timer)
      source.close()
    }
  }, [router, key])
}
