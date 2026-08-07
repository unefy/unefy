package com.unefy.feature.scoring

import com.unefy.core.database.CachedShotEntry
import com.unefy.core.database.CachedShotEntryDao
import com.unefy.core.database.PendingShotEntry
import com.unefy.core.database.PendingShotEntryDao
import com.unefy.core.database.SyncedMemberDao
import com.unefy.core.model.scoring.PlacedShot
import com.unefy.core.model.scoring.ShotSeriesDraft
import com.unefy.core.model.scoring.TargetGeometry
import com.unefy.core.model.scoring.TargetGeometrySeed
import com.unefy.core.network.ApiClient
import com.unefy.core.network.ApiEndpoints
import com.unefy.core.network.ApiResult
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

// --- Wire format ---

/**
 * One shot as sent to the server.
 *
 * `ring` travels too, even though the server recomputes it and ignores what it
 * is told: the backend compares the two and logs a mismatch, which is the only
 * warning that the Kotlin and Python scoring engines have drifted apart.
 */
@Serializable
internal data class ShotPositionDto(
    val x: Double,
    val y: Double,
    @SerialName("caliber_mm") val caliberMm: Double? = null,
    val ring: Int? = null,
    /**
     * Where this shot came from — `scan` if the photo detector proposed it,
     * `manual` if a person placed or corrected it. Per shot, because one series
     * holds both, and the pair is what makes the detector measurable against
     * real sheets.
     */
    val source: String? = null,
)

@Serializable
internal data class ShotEntryUpdateDto(
    val shots: List<ShotPositionDto>,
    @SerialName("target_type") val targetType: String? = null,
    @SerialName("caliber_mm") val caliberMm: Double? = null,
)

@Serializable
internal data class ShotEntryCreateDto(
    val id: String,
    @SerialName("member_id") val memberId: String,
    @SerialName("session_id") val sessionId: String? = null,
    @SerialName("occurred_on") val occurredOn: String? = null,
    val discipline: String? = null,
    @SerialName("target_type") val targetType: String,
    @SerialName("caliber_mm") val caliberMm: Double,
    val shots: List<ShotPositionDto>,
    val source: String,
    @SerialName("recorded_at") val recordedAt: String,
    val notes: String? = null,
)

/**
 * Nullable fields are `T? = null`, never a defaulted non-null: an explicit
 * `null` from the server throws mid-decode where a default only covers absence.
 * See the same note in `CompetitionsRepository`.
 */
@Serializable
internal data class ShotDetailDto(
    val x: Double,
    val y: Double,
    val ring: Int,
    // Nullable rather than defaulted-non-null even though the server always
    // sends these: they carry a default server-side, so the contract marks them
    // optional, and a default only covers absence — an explicit null would throw
    // mid-decode. The fallback lives at the mapping site instead.
    @SerialName("inner_ten") val innerTen: Boolean? = null,
    @SerialName("caliber_mm") val caliberMm: Double? = null,
    val source: String? = null,
)

@Serializable
internal data class EntryDetailsDto(
    val shots: List<ShotDetailDto> = emptyList(),
    @SerialName("target_type") val targetType: String? = null,
    @SerialName("caliber_mm") val caliberMm: Double? = null,
    @SerialName("inner_tens") val innerTens: Int? = null,
    @SerialName("grouping_mm") val groupingMm: Double? = null,
)

@Serializable
internal data class EntryDto(
    val id: String,
    @SerialName("session_id") val sessionId: String,
    @SerialName("member_id") val memberId: String,
    @SerialName("score_value") val scoreValue: Double,
    @SerialName("score_unit") val scoreUnit: String,
    val discipline: String? = null,
    val details: EntryDetailsDto? = null,
    val source: String,
    @SerialName("recorded_by") val recordedBy: String? = null,
    @SerialName("recorded_at") val recordedAt: String,
    val notes: String? = null,
    @SerialName("created_at") val createdAt: String,
    @SerialName("updated_at") val updatedAt: String,
)

@Serializable
internal data class MemberMeDto(
    val id: String,
    @SerialName("first_name") val firstName: String,
    @SerialName("last_name") val lastName: String,
)

@Serializable
internal data class TargetTypeDto(
    val id: String,
    val slug: String,
    val name: String,
    @SerialName("ring_diameters_mm") val ringDiametersMm: List<Double>,
    @SerialName("inner_ten_diameter_mm") val innerTenDiameterMm: Double,
    @SerialName("black_diameter_mm") val blackDiameterMm: Double,
    @SerialName("caliber_diameter_mm") val caliberDiameterMm: Double,
    @SerialName("caliber_name") val caliberName: String? = null,
    @SerialName("distance_m") val distanceM: Int,
    val source: String? = null,
    @SerialName("is_active") val isActive: Boolean,
)

internal fun TargetTypeDto.toGeometry() = TargetGeometry(
    slug = slug,
    name = name,
    ringDiametersMm = ringDiametersMm,
    innerTenDiameterMm = innerTenDiameterMm,
    blackDiameterMm = blackDiameterMm,
    defaultCaliberMm = caliberDiameterMm,
    caliberName = caliberName,
    distanceM = distanceM,
)

// --- Domain ---

/** A recorded series, whether it has reached the server or not. */
data class ShotSeries(
    val id: String,
    val memberId: String,
    val memberLabel: String?,
    val discipline: String?,
    val targetTypeSlug: String?,
    val caliberMm: Double?,
    val total: Int,
    val innerTens: Int?,
    val groupingMm: Double?,
    val shots: List<PlacedShot>,
    val recordedAt: String,
    val notes: String?,
    /** Still in the queue: shown as pending, and editable until it is sent. */
    val pending: Boolean,
    val lastError: String? = null,
) {
    val geometry: TargetGeometry?
        get() = targetTypeSlug?.let { TargetGeometrySeed.bySlug(it) }
}

/**
 * Merges the queue and the cache into the one list a screen shows.
 *
 * Extracted as a plain function so it can be tested directly. The rule it
 * encodes: queued series come first and unconditionally — a series recorded five
 * minutes ago in a basement must be visible even though the server has never
 * heard of it — and a cached row whose id is already queued is dropped. That
 * last part matters in the window between a successful send and the next
 * refresh, where the same series exists in both and would otherwise be listed
 * twice, looking like the shooter recorded it two times.
 */
internal fun mergeSeries(pending: List<ShotSeries>, cached: List<ShotSeries>): List<ShotSeries> {
    val queuedIds = pending.mapTo(mutableSetOf()) { it.id }
    return pending + cached.filterNot { it.id in queuedIds }
}

/** One member a series can be recorded for. */
data class MemberOption(val id: String, val label: String)

interface ScoringRepository {
    /** Targets to choose from — the server's catalog, or the built-in seed. */
    suspend fun targetTypes(): List<TargetGeometry>

    /** The club's members, from the synced mirror. Empty before a first sync. */
    suspend fun selectableMembers(): List<MemberOption>

    /** The caller's own member record, when their account is linked to one. */
    suspend fun ownMember(): MemberOption?

    /** Queue a series. Always succeeds locally; sending happens later. */
    suspend fun record(
        draft: ShotSeriesDraft,
        memberId: String,
        memberLabel: String?,
        sessionId: String?,
        occurredOn: String,
        discipline: String?,
        recordedAt: String,
        notes: String?,
    ): String

    /** Everything the caller has recorded, queued rows first. */
    fun myHistory(): Flow<List<ShotSeries>>

    fun pendingCount(): Flow<Int>

    /** Pull the caller's own entries from the server into the cache. */
    /**
     * Replace the shots of a series that was already recorded.
     *
     * Two paths, because a series lives in two places: one still in the queue
     * has never been sent and is rewritten locally, one already on the server
     * is corrected there and rescored by it. The second needs a connection —
     * queueing corrections as well would mean reconciling two edits of the same
     * series made on two devices, which is a different problem and not one a
     * shooting bench has.
     */
    suspend fun correct(seriesId: String, draft: ShotSeriesDraft): ApiResult<Unit>

    /**
     * Withdraw a recorded series.
     *
     * Like [correct], two paths: one still queued has never left the device and
     * is simply dropped, one already sent is withdrawn on the server, which
     * keeps it soft-deleted. The second needs a connection.
     */
    suspend fun delete(seriesId: String): ApiResult<Unit>

    suspend fun refreshHistory(): ApiResult<Unit>

    /** Try to send everything queued. Returns how many made it. */
    suspend fun drainQueue(): Int

    suspend fun discardPending(id: String)
}

@Singleton
internal class DefaultScoringRepository @Inject constructor(
    private val apiClient: ApiClient,
    private val pendingDao: PendingShotEntryDao,
    private val cacheDao: CachedShotEntryDao,
    private val memberDao: SyncedMemberDao,
) : ScoringRepository {

    private val json = Json { ignoreUnknownKeys = true; encodeDefaults = true }

    override suspend fun targetTypes(): List<TargetGeometry> =
        when (val result = apiClient.get<List<TargetTypeDto>>(ApiEndpoints.TARGET_TYPES)) {
            is ApiResult.Success -> result.data.map { it.toGeometry() }
            // The built-in seed is not a degraded fallback here — it is what
            // makes the app usable on a range that has never had signal.
            is ApiResult.Failure -> TargetGeometrySeed.ALL
        }

    override suspend fun selectableMembers(): List<MemberOption> =
        memberDao.search("").first().map { MemberOption(it.id, "${it.firstName} ${it.lastName}") }

    override suspend fun ownMember(): MemberOption? =
        when (val result = apiClient.get<MemberMeDto>(ApiEndpoints.MEMBERS_ME)) {
            is ApiResult.Success ->
                MemberOption(
                    result.data.id,
                    "${result.data.firstName} ${result.data.lastName}",
                )
            is ApiResult.Failure -> null
        }

    override suspend fun record(
        draft: ShotSeriesDraft,
        memberId: String,
        memberLabel: String?,
        sessionId: String?,
        occurredOn: String,
        discipline: String?,
        recordedAt: String,
        notes: String?,
    ): String {
        val entry = PendingShotEntry(
            memberId = memberId,
            memberLabel = memberLabel,
            sessionId = sessionId,
            // Only sent when there is no session; the server needs one or the other.
            occurredOn = if (sessionId == null) occurredOn else null,
            discipline = discipline,
            targetType = draft.geometry.slug,
            caliberMm = draft.caliberMm,
            shotsJson = json.encodeToString(draft.shots.map(::toDto)),
            localTotal = draft.total,
            recordedAt = recordedAt,
            notes = notes,
        )
        // Written before any network call: the queue is the source of truth, and
        // a series must survive the app being killed the moment after saving.
        pendingDao.insert(entry)
        return entry.id
    }

    override fun myHistory(): Flow<List<ShotSeries>> =
        combinePendingAndCached()

    private fun combinePendingAndCached(): Flow<List<ShotSeries>> =
        kotlinx.coroutines.flow.combine(
            pendingDao.stream(),
            cacheDao.all(),
            memberDao.search(""),
        ) { pending, cached, members ->
            val names = members.associate { it.id to "${it.firstName} ${it.lastName}" }
            mergeSeries(
                pending.map(::toSeries),
                cached.map { toSeries(it, names) },
            )
        }

    override fun pendingCount(): Flow<Int> = pendingDao.countStream()

    override suspend fun correct(seriesId: String, draft: ShotSeriesDraft): ApiResult<Unit> {
        val pending = pendingDao.all().firstOrNull { it.id == seriesId }
        if (pending != null) {
            pendingDao.insert(
                pending.copy(
                    shotsJson = json.encodeToString(draft.shots.map(::toDto)),
                    localTotal = draft.total,
                    targetType = draft.geometry.slug,
                    caliberMm = draft.caliberMm,
                ),
            )
            return ApiResult.Success(Unit)
        }

        val body = ShotEntryUpdateDto(
            shots = draft.shots.map(::toDto),
            targetType = draft.geometry.slug,
            caliberMm = draft.caliberMm,
        )
        return when (val result = apiClient.patch<EntryDto>("${ApiEndpoints.ENTRIES}/$seriesId", body)) {
            is ApiResult.Success -> {
                cacheDao.upsert(listOf(toCached(result.data)))
                ApiResult.Success(Unit)
            }
            is ApiResult.Failure -> ApiResult.Failure(result.error)
        }
    }

    override suspend fun delete(seriesId: String): ApiResult<Unit> {
        if (pendingDao.all().any { it.id == seriesId }) {
            pendingDao.delete(seriesId)
            return ApiResult.Success(Unit)
        }

        return when (
            val result = apiClient.deleteNoContent("${ApiEndpoints.ENTRIES}/$seriesId")
        ) {
            is ApiResult.Success -> {
                cacheDao.deleteById(seriesId)
                ApiResult.Success(Unit)
            }
            is ApiResult.Failure -> ApiResult.Failure(result.error)
        }
    }

    override suspend fun refreshHistory(): ApiResult<Unit> =
        when (val result = apiClient.get<List<EntryDto>>(ApiEndpoints.MY_ENTRIES)) {
            is ApiResult.Success -> {
                cacheDao.replaceAll(result.data.map(::toCached))
                ApiResult.Success(Unit)
            }
            is ApiResult.Failure -> ApiResult.Failure(result.error)
        }

    override suspend fun drainQueue(): Int {
        var sent = 0
        for (entry in pendingDao.all()) {
            val shots = runCatching {
                json.decodeFromString<List<ShotPositionDto>>(entry.shotsJson)
            }.getOrNull()
            if (shots == null) {
                // Unreadable payload: retrying cannot fix it and keeping it
                // would block the queue behind a row that can never drain.
                pendingDao.delete(entry.id)
                continue
            }

            val body = ShotEntryCreateDto(
                id = entry.id,
                memberId = entry.memberId,
                sessionId = entry.sessionId,
                occurredOn = entry.occurredOn,
                discipline = entry.discipline,
                targetType = entry.targetType,
                caliberMm = entry.caliberMm,
                shots = shots,
                source = entry.source,
                recordedAt = entry.recordedAt,
                notes = entry.notes,
            )

            when (val result = apiClient.post<EntryDto>(ApiEndpoints.ENTRIES, body)) {
                is ApiResult.Success -> {
                    cacheDao.upsert(listOf(toCached(result.data)))
                    pendingDao.delete(entry.id)
                    sent++
                }
                is ApiResult.Failure -> {
                    pendingDao.recordFailure(entry.id, result.error.toString())
                    // Stop at the first failure rather than hammering every row
                    // against a network that is plainly not there.
                    break
                }
            }
        }
        return sent
    }

    override suspend fun discardPending(id: String) = pendingDao.delete(id)

    // --- Mapping ---

    private fun toDto(shot: PlacedShot) = ShotPositionDto(
        x = shot.x,
        y = shot.y,
        caliberMm = shot.caliberMm,
        ring = shot.ring,
        source = shot.source,
    )

    private fun toCached(dto: EntryDto) = CachedShotEntry(
        id = dto.id,
        sessionId = dto.sessionId,
        memberId = dto.memberId,
        scoreValue = dto.scoreValue,
        scoreUnit = dto.scoreUnit,
        discipline = dto.discipline,
        targetType = dto.details?.targetType,
        caliberMm = dto.details?.caliberMm,
        shotsJson = dto.details?.shots?.let { json.encodeToString(it) },
        innerTens = dto.details?.innerTens,
        groupingMm = dto.details?.groupingMm,
        source = dto.source,
        recordedAt = dto.recordedAt,
        notes = dto.notes,
    )

    private fun toSeries(row: PendingShotEntry) = ShotSeries(
        id = row.id,
        memberId = row.memberId,
        memberLabel = row.memberLabel,
        discipline = row.discipline,
        targetTypeSlug = row.targetType,
        caliberMm = row.caliberMm,
        total = row.localTotal,
        innerTens = null,
        groupingMm = null,
        shots = decodePending(row.shotsJson, row.caliberMm),
        recordedAt = row.recordedAt,
        notes = row.notes,
        pending = true,
        lastError = row.lastError,
    )

    private fun toSeries(row: CachedShotEntry, names: Map<String, String>) = ShotSeries(
        id = row.id,
        memberId = row.memberId,
        // Resolved from the member mirror rather than carried on the entry: the
        // server answers with member ids, and a list that cannot say whose shots
        // these are is unreadable the moment somebody records for a second
        // person. Null while the mirror is still empty on a fresh device.
        memberLabel = names[row.memberId],
        discipline = row.discipline,
        targetTypeSlug = row.targetType,
        caliberMm = row.caliberMm,
        total = row.scoreValue.toInt(),
        innerTens = row.innerTens,
        groupingMm = row.groupingMm,
        shots = decodeCached(row.shotsJson),
        recordedAt = row.recordedAt,
        notes = row.notes,
        pending = false,
    )

    /**
     * A malformed payload yields an empty shot list rather than an exception:
     * the series still has a total and a date, and a history screen that
     * crashes is worse than one missing a picture.
     */
    private fun decodePending(raw: String, seriesCaliber: Double): List<PlacedShot> =
        runCatching {
            json.decodeFromString<List<ShotPositionDto>>(raw).mapIndexed { index, dto ->
                PlacedShot(
                    id = index.toString(),
                    x = dto.x,
                    y = dto.y,
                    ring = dto.ring ?: 0,
                    caliberMm = dto.caliberMm ?: seriesCaliber,
                )
            }
        }.getOrDefault(emptyList())

    private fun decodeCached(raw: String?): List<PlacedShot> {
        if (raw == null) return emptyList()
        return runCatching {
            json.decodeFromString<List<ShotDetailDto>>(raw).mapIndexed { index, dto ->
                PlacedShot(
                    id = index.toString(),
                    x = dto.x,
                    y = dto.y,
                    ring = dto.ring,
                    innerTen = dto.innerTen ?: false,
                    caliberMm = dto.caliberMm,
                )
            }
        }.getOrDefault(emptyList())
    }
}

@Module
@InstallIn(SingletonComponent::class)
internal abstract class ScoringModule {
    @Binds
    abstract fun bindScoringRepository(impl: DefaultScoringRepository): ScoringRepository

    @Binds
    abstract fun bindSeriesScans(impl: ScanStore): SeriesScans
}
