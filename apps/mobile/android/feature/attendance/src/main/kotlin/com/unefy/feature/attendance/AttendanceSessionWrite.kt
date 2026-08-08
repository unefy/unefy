package com.unefy.feature.attendance

import com.unefy.core.database.CachedSession
import com.unefy.core.database.CachedSessionDao
import com.unefy.core.network.ApiClient
import com.unefy.core.network.ApiEndpoints
import com.unefy.core.network.ApiResult
import com.unefy.core.database.PendingWrite
import com.unefy.core.sync.PendingWriteHandler
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import dagger.multibindings.IntoSet
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.serialization.json.Json

/**
 * The queue entity for an evening opened without a connection.
 *
 * Not a sync collection: attendance sessions are not mirrored, so there is no
 * `/sync/attendance-sessions` this could be named after. The string only has
 * to be stable, because it is what a queued row is filed under across app
 * restarts.
 */
internal const val SESSION_WRITE_ENTITY = "attendance-sessions"

/**
 * Sends an evening that was opened at the range.
 *
 * The server accepts the id the phone chose and answers a replay with the same
 * session, so a drain that dies after the insert but before the row was
 * deleted cannot open a second evening beside the first one's records.
 */
@Singleton
class AttendanceSessionWriteHandler @Inject constructor(
    private val apiClient: ApiClient,
    private val sessionCache: CachedSessionDao,
    private val json: Json,
) : PendingWriteHandler {

    override val entity = SESSION_WRITE_ENTITY

    override suspend fun send(write: PendingWrite): ApiResult<Unit> {
        val payload = json.decodeFromString<CreateSessionRequest>(write.payloadJson)
        return when (
            val result =
                apiClient.post<AttendanceSessionDto>(ApiEndpoints.ATTENDANCE_SESSIONS, payload)
        ) {
            is ApiResult.Success -> {
                // The server's version, over the one this device guessed: it
                // carries the record count and whatever the backend settled on
                // for the window.
                sessionCache.upsert(listOf(result.data.toCached()))
                ApiResult.Success(Unit)
            }

            is ApiResult.Failure -> ApiResult.Failure(result.error)
        }
    }
}

internal fun AttendanceSessionDto.toCached() = CachedSession(
    id = id,
    title = title,
    location = location,
    recordCount = recordCount,
    opensAtEpochSeconds = parseIsoSeconds(opensAt),
    closesAtEpochSeconds = parseIsoSeconds(closesAt),
)

@Module
@InstallIn(SingletonComponent::class)
abstract class AttendanceSessionWriteModule {
    @Binds
    @IntoSet
    abstract fun bindSessionWriteHandler(
        impl: AttendanceSessionWriteHandler,
    ): PendingWriteHandler
}

/** Seconds for an ISO instant. Unparseable means 0 — never a crash. */
internal fun parseIsoSeconds(value: String): Long =
    runCatching { java.time.Instant.parse(value).epochSecond }.getOrDefault(0L)
