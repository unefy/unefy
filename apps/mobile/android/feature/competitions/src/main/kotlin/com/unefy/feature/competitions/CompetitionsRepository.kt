package com.unefy.feature.competitions

import com.unefy.core.database.DISCIPLINES_SEPARATOR
import com.unefy.core.database.SyncCursorDao
import com.unefy.core.database.SyncedCompetition
import com.unefy.core.database.SyncedCompetitionDao
import com.unefy.core.model.Competition
import com.unefy.core.model.Scoreboard
import com.unefy.core.model.ScoreboardRow
import com.unefy.core.network.ApiClient
import com.unefy.core.network.ApiEndpoints
import com.unefy.core.network.ApiResult
import com.unefy.core.network.map
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
internal data class CompetitionDto(
    val id: String,
    val name: String,
    val description: String? = null,
    @SerialName("competition_type") val competitionType: String? = null,
    @SerialName("start_date") val startDate: String = "",
    @SerialName("end_date") val endDate: String? = null,
    @SerialName("scoring_unit") val scoringUnit: String = "",
    @SerialName("scoring_mode") val scoringMode: String = "highest_wins",
    val disciplines: List<String> = emptyList(),
)

internal fun CompetitionDto.toDomain() = Competition(
    id = id,
    name = name,
    description = description,
    type = competitionType,
    startDate = startDate,
    endDate = endDate,
    scoringUnit = scoringUnit,
    scoringMode = scoringMode,
    disciplines = disciplines,
)

/**
 * The whole scoreboard body, not just its `data`.
 *
 * The backend puts `scoring_unit` and `scoring_mode` beside `data` rather than
 * inside `meta`, and both are needed to render a ranking that means anything.
 */
@Serializable
internal data class ScoreboardEnvelopeDto(
    val data: List<ScoreboardRowDto> = emptyList(),
    @SerialName("scoring_unit") val scoringUnit: String = "",
    @SerialName("scoring_mode") val scoringMode: String = "highest_wins",
)

@Serializable
internal data class ScoreboardRowDto(
    val rank: Int = 0,
    @SerialName("member_id") val memberId: String = "",
    @SerialName("member_name") val memberName: String = "",
    @SerialName("total_score") val totalScore: Double = 0.0,
    @SerialName("best_score") val bestScore: Double = 0.0,
    @SerialName("average_score") val averageScore: Double = 0.0,
    @SerialName("entry_count") val entryCount: Int = 0,
)

internal fun ScoreboardEnvelopeDto.toDomain() = Scoreboard(
    unit = scoringUnit,
    highestWins = scoringMode == "highest_wins",
    rows = data.map {
        ScoreboardRow(
            rank = it.rank,
            memberId = it.memberId,
            memberName = it.memberName,
            totalScore = it.totalScore,
            bestScore = it.bestScore,
            averageScore = it.averageScore,
            entryCount = it.entryCount,
        )
    },
)

/** A mirror row as the domain model. */
internal fun SyncedCompetition.toDomain() = Competition(
    id = id,
    name = name,
    description = description,
    type = competitionType,
    startDate = startDate,
    endDate = endDate,
    scoringUnit = scoringUnit,
    scoringMode = scoringMode,
    disciplines = if (disciplines.isEmpty()) {
        emptyList()
    } else {
        disciplines.split(DISCIPLINES_SEPARATOR)
    },
)

interface CompetitionsRepository {
    /** The competition list, from the local mirror, newest first. */
    fun stream(): Flow<List<Competition>>

    /** Whether the mirror holds the whole collection — see MembersRepository. */
    fun hasSynced(): Flow<Boolean>

    /** The live ranking. Online-only: a stale ranking shown as current would be
     * worse than a spinner, and the server owns the aggregation. */
    suspend fun scoreboard(competitionId: String): ApiResult<Scoreboard>
}

@Singleton
class DefaultCompetitionsRepository @Inject constructor(
    private val apiClient: ApiClient,
    private val competitions: SyncedCompetitionDao,
    private val cursors: SyncCursorDao,
) : CompetitionsRepository {

    override fun stream(): Flow<List<Competition>> =
        competitions.all().map { rows -> rows.map(SyncedCompetition::toDomain) }

    override fun hasSynced(): Flow<Boolean> =
        cursors.bootstrapCompleteStream(CompetitionSyncCollection.COLLECTION)

    override suspend fun scoreboard(competitionId: String): ApiResult<Scoreboard> = apiClient
        .getWhole<ScoreboardEnvelopeDto>(ApiEndpoints.competitionScoreboard(competitionId))
        .map(ScoreboardEnvelopeDto::toDomain)
}

@Module
@InstallIn(SingletonComponent::class)
abstract class CompetitionsModule {
    @Binds
    abstract fun bindCompetitionsRepository(
        impl: DefaultCompetitionsRepository,
    ): CompetitionsRepository
}
