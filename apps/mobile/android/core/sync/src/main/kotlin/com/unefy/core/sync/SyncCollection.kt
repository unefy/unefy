package com.unefy.core.sync

import kotlinx.serialization.json.JsonElement

/**
 * One mirrored collection, from the sync engine's point of view.
 *
 * Features register an implementation with Hilt `@IntoSet` (the precedent is
 * `AttendanceSignOut`), which keeps the direction of dependency right: the engine
 * knows about pages, cursors and generations, and nothing about what a member
 * looks like. It hands over raw JSON and the feature decodes it with the DTO it
 * already maintains against the OpenAPI spec.
 *
 * Every method here is called inside the engine's transaction, so implementations
 * must not start one of their own.
 */
interface SyncCollection {

    /**
     * The collection name, which is three things at once: the path segment of
     * `GET /api/v1/sync/{name}`, the value the server lists in
     * `/sync/manifest`, and the `entity` field of a change hint on the stream.
     * They are the same string on purpose — see `collection_for_model` in
     * backend/app/sync/registry.py. Plural: "members", not "member".
     */
    val name: String

    /**
     * Applies one page. [changed] are full rows to upsert, [deleted] are ids to
     * remove, [generation] is the stamp every written row carries.
     *
     * A row appearing twice across pages is normal and must be harmless — the
     * server guarantees its pages are a *superset* of what changed, never a
     * subset, and pays for that with duplicates. Upsert, never insert.
     */
    suspend fun apply(changed: List<JsonElement>, deleted: List<String>, generation: Long)

    /**
     * Drops rows older than [generation], after a bootstrap has drained fully.
     *
     * The only way a hard-deleted row leaves the device: a soft delete arrives as
     * a tombstone, a hard delete leaves nothing behind to announce it.
     */
    suspend fun sweep(generation: Long)

    /** Everything this collection holds. Called when an account signs out. */
    suspend fun clear()
}
