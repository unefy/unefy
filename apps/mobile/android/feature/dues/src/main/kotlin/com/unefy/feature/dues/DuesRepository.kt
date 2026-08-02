package com.unefy.feature.dues

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
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
internal data class DuesDto(
    val id: String,
    @SerialName("member_id") val memberId: String = "",
    @SerialName("member_name") val memberName: String = "",
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
    memberName = memberName,
    feeName = feeName,
    amount = amount,
    dueDate = dueDate,
    status = DuesStatus.fromApi(status),
    paidAt = paidAt,
)

internal fun DuesSummaryDto.toDomain() =
    DuesSummary(openCount, openAmount, paidCount, paidAmount)

interface DuesRepository {
    /** Administrative: every member's dues, board and above only. */
    suspend fun list(page: Int = 1, perPage: Int = 50): ApiResult<List<DuesEntry>>

    /** Self-service: the caller's own dues. */
    suspend fun mine(page: Int = 1, perPage: Int = 50): ApiResult<List<DuesEntry>>

    suspend fun summary(): ApiResult<DuesSummary>
}

@Singleton
class DefaultDuesRepository @Inject constructor(
    private val apiClient: ApiClient,
) : DuesRepository {
    override suspend fun list(page: Int, perPage: Int): ApiResult<List<DuesEntry>> = apiClient
        .get<List<DuesDto>>(ApiEndpoints.DUES) {
            parameter("page", page)
            parameter("per_page", perPage)
        }
        .map { dtos -> dtos.map(DuesDto::toDomain) }

    override suspend fun mine(page: Int, perPage: Int): ApiResult<List<DuesEntry>> = apiClient
        .get<List<DuesDto>>(ApiEndpoints.DUES_ME) {
            parameter("page", page)
            parameter("per_page", perPage)
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
