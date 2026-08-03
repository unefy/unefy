package com.unefy.core.push

/**
 * A feature's window onto a background drain: state before, verdict after.
 *
 * This is how local notifications happen without content ever passing through
 * Google — the wake-up carries ids only, the drain pulls the real rows through
 * the role-checked sync endpoints, and an observer diffs its own mirror and
 * renders whatever it finds, on the device.
 *
 * Background only, on purpose: [WakeupDrain] runs solely from the FCM worker.
 * A foreground change reaches the user through the live list — a notification
 * on top of a screen already showing the change would be noise.
 *
 * Registered via Hilt `@IntoSet`, like [com.unefy.core.sync.SyncCollection] —
 * core:push never learns which features observe.
 */
interface BackgroundSyncObserver {

    /** Called before the drain, to snapshot whatever the diff will need. */
    suspend fun beforeDrain()

    /** Called after a completed drain. Diff, decide, notify — or do nothing. */
    suspend fun afterDrain()
}
