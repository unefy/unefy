package com.unefy.feature.dues

import com.unefy.core.database.DueWithMemberName
import com.unefy.core.database.SyncCursorDao
import com.unefy.core.database.SyncedDueDao
import com.unefy.core.model.DuesEntry
import com.unefy.core.model.DuesStatus
import com.unefy.core.model.DuesSummary
import com.unefy.core.network.ApiClient
import com.unefy.core.network.ApiEndpoints
import com.unefy.core.network.ApiResult
import com.unefy.core.network.map
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import io.ktor.client.request.parameter
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
internal data class DuesDto(
    val id: String,
    @SerialName("member_id") val memberId: String = "",
    /**
     * Nullable, not defaulted-empty: the sync payload carries an explicit
     * `member_name: null` (the merge only happens on the list endpoints), and
     * an explicit null does not fall back to a default — it threw, mid-apply,
     * and the dues mirror never filled.
     */
    @SerialName("member_name") val memberName: String? = null,
    @SerialName("fee_name") val feeName: String = "",
    val amount: String = "0",
    @SerialName("due_date") val dueDate: String? = null,
    val status: String? = null,
    @SerialName("paid_at") val paidAt: String? = null,
)

@Serializable
internal data class DuesSummaryDto(
    @SerialName("open_count") val openCount: Int = 0,
    @SerialName("open_amount") val openAmount: String = "0",
    @SerialName("paid_count") val paidCount: Int = 0,
    @SerialName("paid_amount") val paidAmount: String = "0",
)

internal fun DuesDto.toDomain() = DuesEntry(
    id = id,
    memberId = memberId,
    memberName = memberName.orEmpty(),
    feeName = feeName,
    amount = amount,
    dueDate = dueDate,
    status = DuesStatus.fromApi(status),
    paidAt = paidAt,
)

internal fun DuesSummaryDto.toDomain() =
    DuesSummary(openCount, openAmount, paidCount, paidAmount)

/** A mirror row as the domain model — the name arrives from the member join. */
internal fun DueWithMemberName.toDomain() = DuesEntry(
    id = id,
    memberId = memberId,
    memberName = memberName,
    feeName = feeName,
    amount = amount,
    dueDate = dueDate,
    status = DuesStatus.fromApi(status),
    paidAt = paidAt,
)

interface DuesRepository {
    /**
     * Administrative: every member's dues, from the local mirror, board and
     * above only (a plain member's sync is refused and latched, so the mirror
     * simply stays empty for them).
     *
     * @param status one of the backend's `open`, `paid`, `cancelled`, or null
     *   for all of them. Filtered in SQL — the local counterpart of the server
     *   filter the chips used to reload with: "offen" means every open due in
     *   the ledger, not the open ones among the rows on screen.
     */
    fun stream(status: String? = null): Flow<List<DuesEntry>>

    /** Whether the dues mirror holds the whole ledger — see MembersRepository. */
    fun hasSynced(): Flow<Boolean>

    /** Self-service: the caller's own dues. Online — see the plan: a plain
     * member may not sync the dues collection, so this stays a paged request. */
    suspend fun mine(
        page: Int = 1,
        perPage: Int = 50,
        status: String? = null,
    ): ApiResult<List<DuesEntry>>

    /** The club-wide totals. Deliberately online-only: one implementation of
     * the money arithmetic, on the server. Offline the header is hidden. */
    suspend fun summary(): ApiResult<DuesSummary>
}

@Singleton
class DefaultDuesRepository @Inject constructor(
    private val apiClient: ApiClient,
    private val dues: SyncedDueDao,
    private val cursors: SyncCursorDao,
) : DuesRepository {
    override fun stream(status: String?): Flow<List<DuesEntry>> =
        dues.withMemberNames(status).map { rows -> rows.map(DueWithMemberName::toDomain) }

    override fun hasSynced(): Flow<Boolean> =
        cursors.bootstrapCompleteStream(DuesSyncCollection.COLLECTION)

    override suspend fun mine(
        page: Int,
        perPage: Int,
        status: String?,
    ): ApiResult<List<DuesEntry>> = apiClient
        .get<List<DuesDto>>(ApiEndpoints.DUES_ME) {
            parameter("page", page)
            parameter("per_page", perPage)
            status?.let { parameter("status", it) }
        }
        .map { dtos -> dtos.map(DuesDto::toDomain) }

    override suspend fun summary(): ApiResult<DuesSummary> = apiClient
        .get<DuesSummaryDto>(ApiEndpoints.DUES_SUMMARY)
        .map(DuesSummaryDto::toDomain)
}

@Module
@InstallIn(SingletonComponent::class)
abstract class DuesModule {
    @Binds
    abstract fun bindDuesRepository(impl: DefaultDuesRepository): DuesRepository
}
