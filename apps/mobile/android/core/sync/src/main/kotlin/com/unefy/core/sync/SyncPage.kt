package com.unefy.core.sync

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

/**
 * One page of `GET /api/v1/sync/{collection}`.
 *
 * **Why this is not decoded as [com.unefy.core.network.ApiEnvelope].** Sync
 * answers `{"data": {...}, "meta": {"sync": {...}}}` — `data` is an object rather
 * than a list, and the metadata is nested a level deeper than every other list
 * route's. `ApiMeta` has a default for every field, so decoding this envelope as
 * one would succeed and hand back a meta of all zeroes: no cursor, `has_more`
 * false, and a sync that silently believes it is finished after one page. Hence a
 * type of its own, fetched through `ApiClient.getWhole`, which exists for exactly
 * this (the scoreboard has the same problem).
 *
 * `changed` stays as raw [JsonElement]: the shape of a member is
 * `feature:members`' business, and decoding it here would drag every feature's
 * DTOs into this module.
 */
@Serializable
data class SyncPage(
    val data: SyncData,
    val meta: SyncEnvelopeMeta,
)

@Serializable
data class SyncData(
    val changed: List<JsonElement> = emptyList(),
    val deleted: List<SyncTombstone> = emptyList(),
)

/**
 * A row that is gone: id and time, never the row body.
 *
 * The backend's reasoning, which this side inherits: a tombstone carrying a
 * deleted member's name and bank details, handed to every device in the club and
 * kept there for a fortnight, would be a second copy of the personal data the
 * deletion was meant to remove. The id is all a client needs to delete locally.
 */
@Serializable
data class SyncTombstone(
    val id: String,
    @SerialName("deleted_at") val deletedAt: String? = null,
)

@Serializable
data class SyncEnvelopeMeta(val sync: SyncMeta)

@Serializable
data class SyncMeta(
    /** Opaque. Store it, hand it back, never parse it. */
    val cursor: String,
    @SerialName("has_more") val hasMore: Boolean = false,
    @SerialName("server_time") val serverTime: String? = null,
    val collection: String? = null,
)
