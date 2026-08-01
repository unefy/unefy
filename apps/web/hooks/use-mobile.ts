import * as React from "react"

const MOBILE_BREAKPOINT = 768

function subscribe(onStoreChange: () => void) {
  const mql = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`)
  mql.addEventListener("change", onStoreChange)
  return () => mql.removeEventListener("change", onStoreChange)
}

const getSnapshot = () => window.innerWidth < MOBILE_BREAKPOINT

// Rendered server-side there is no viewport, so assume desktop and let the
// first client snapshot correct it.
const getServerSnapshot = () => false

/**
 * Subscribes to the mobile breakpoint via `useSyncExternalStore` rather than
 * mirroring `matchMedia` into state inside an effect — the snapshot is read
 * during render, so there is no post-mount state write.
 */
export function useIsMobile() {
  return React.useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot)
}
