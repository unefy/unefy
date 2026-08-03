package com.unefy.feature.competitions

import com.unefy.core.database.DISCIPLINES_SEPARATOR
import com.unefy.core.database.SyncedCompetition
import com.unefy.core.database.SyncedCompetitionDao
import com.unefy.core.sync.SyncCollection
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import dagger.multibindings.IntoSet
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement

/**
 * Turns a page of `/api/v1/sync/competitions` into rows in the local mirror.
 * The scoreboard is not part of this — it stays a live server aggregate.
 */
@Singleton
class CompetitionSyncCollection @Inject constructor(
    private val dao: SyncedCompetitionDao,
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
                json.decodeFromJsonElement(CompetitionDto.serializer(), it).toRow(generation)
            },
        )
        dao.deleteByIds(deleted)
    }

    override suspend fun sweep(generation: Long) = dao.sweep(generation)

    override suspend fun clear() = dao.deleteAll()

    companion object {
        /** Sync path segment and `entity` value on the change stream. */
        const val COLLECTION = "competitions"
    }
}

@Module
@InstallIn(SingletonComponent::class)
abstract class CompetitionSyncModule {
    @Binds
    @IntoSet
    abstract fun bindCompetitionSyncCollection(impl: CompetitionSyncCollection): SyncCollection
}

/** The DTO as a mirror row. Disciplines join with the shared separator. */
internal fun CompetitionDto.toRow(generation: Long) = SyncedCompetition(
    id = id,
    name = name,
    description = description,
    competitionType = competitionType,
    startDate = startDate,
    endDate = endDate,
    scoringUnit = scoringUnit,
    scoringMode = scoringMode,
    disciplines = disciplines.orEmpty().joinToString(DISCIPLINES_SEPARATOR),
    generation = generation,
)
