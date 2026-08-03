"use client"

import { useEffect, useRef } from "react"
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

  // The filter lives in a ref, not in the effect: the connection must survive a
  // filter change. A shell-wide caller derives its collections from the current
  // route, so tying the EventSource's lifetime to the filter would tear down and
  // re-open the connection on every navigation. That is not a subtle
  // inefficiency: reconnect storms are what the backend's per-user stream cap
  // exists to stop, so a user clicking through three pages would lock
  // themselves out of live updates.
  const collectionsRef = useRef<readonly string[] | null>(null)

  // Keyed on the contents, not the array: callers pass a literal, which is a
  // new object every render, and keying on identity would re-run this on each.
  const key = options?.collections?.join(",") ?? ""
  useEffect(() => {
    collectionsRef.current = key === "" ? null : key.split(",")
  }, [key])

  useEffect(() => {
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
      const collections = collectionsRef.current
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
  }, [router])
}
