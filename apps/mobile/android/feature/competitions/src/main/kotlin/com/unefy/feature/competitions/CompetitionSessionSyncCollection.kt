package com.unefy.feature.competitions

import com.unefy.core.database.SyncedCompetitionSession
import com.unefy.core.database.SyncedCompetitionSessionDao
import com.unefy.core.sync.SyncCollection
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import dagger.multibindings.IntoSet
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement

/**
 * The wire shape of a round, as `SessionResponse` sends it.
 *
 * `name`, `location`, `discipline` and `event_id` are typed `str | null` on the
 * server, so they are nullable here rather than defaulted-empty: an explicit
 * null does not fall back to a default, it throws mid-decode. Same lesson as
 * the competition mirror's `disciplines`.
 */
@Serializable
internal data class CompetitionSessionDto(
    val id: String,
    @SerialName("competition_id") val competitionId: String,
    val name: String? = null,
    val date: String = "",
    val location: String? = null,
    val discipline: String? = null,
    @SerialName("event_id") val eventId: String? = null,
)

/** Turns a page of `/api/v1/sync/competition-sessions` into mirror rows. */
@Singleton
class CompetitionSessionSyncCollection @Inject constructor(
    private val dao: SyncedCompetitionSessionDao,
    private val json: Json,
) : SyncCollection {

    override val name = COLLECTION

    override suspend fun apply(
        changed: List<JsonElement>,
        deleted: List<String>,
        generation: Long,
    ) {
        dao.upsert(
            changed.map {
                json.decodeFromJsonElement(CompetitionSessionDto.serializer(), it)
                    .toRow(generation)
            },
        )
        dao.deleteByIds(deleted)
    }

    override suspend fun sweep(generation: Long) = dao.sweep(generation)

    override suspend fun clear() = dao.deleteAll()

    companion object {
        /** Sync path segment and `entity` value on the change stream. */
        const val COLLECTION = "competition-sessions"
    }
}

@Module
@InstallIn(SingletonComponent::class)
abstract class CompetitionSessionSyncModule {
    @Binds
    @IntoSet
    abstract fun bindCompetitionSessionSyncCollection(
        impl: CompetitionSessionSyncCollection,
    ): SyncCollection
}

internal fun CompetitionSessionDto.toRow(generation: Long) = SyncedCompetitionSession(
    id = id,
    competitionId = competitionId,
    name = name,
    date = date,
    location = location,
    discipline = discipline,
    eventId = eventId,
    generation = generation,
)
