package com.unefy.core.network

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * The backend wraps every response as `{ "data": ... }` on success and
 * `{ "error": { "code", "message" } }` on failure. List endpoints add `meta`.
 * See backend/app/core/exceptions.py and backend/app/api/v1/members.py.
 */
@Serializable
data class ApiEnvelope<T>(
    val data: T? = null,
    val error: ApiErrorBody? = null,
    val meta: ApiMeta? = null,
)

@Serializable
data class ApiErrorBody(
    val code: String,
    val message: String,
)

@Serializable
data class ApiMeta(
    val total: Int = 0,
    val page: Int = 1,
    @SerialName("per_page") val perPage: Int = 20,
    @SerialName("total_pages") val totalPages: Int = 1,
)

/**
 * Whether a page follows the one this meta describes.
 *
 * Every list endpoint caps `per_page` at 100, so "just ask for everything" is
 * not an option — a list that does not page stops at its first page and says
 * nothing about the rest.
 *
 * A missing meta counts as no. Guessing "maybe" would have the list ask for a
 * page that never comes, forever, against a backend that stopped sending it.
 */
fun ApiMeta?.hasNextPage(): Boolean = this != null && page < totalPages

/**
 * Typed failures. The UI maps these to messages — no raw exception strings or
 * HTTP codes ever reach a screen.
 */
sealed interface ApiError {
    /** No connectivity, DNS failure, timeout. Retrying may help. */
    data class Network(val cause: Throwable) : ApiError

    /** 401 that survived a token refresh — the session is genuinely gone. */
    data object Unauthorized : ApiError

    /** 403. Deliberately distinct from [Unauthorized]: signing in again will not help. */
    data object Forbidden : ApiError

    data class NotFound(val code: String?) : ApiError

    /** Any other non-2xx, carrying the backend's machine-readable code. */
    data class Http(val status: Int, val code: String?, val message: String?) : ApiError

    /** The response did not match the expected shape — a backend contract drift. */
    data class Serialization(val cause: Throwable) : ApiError

    data class Unknown(val cause: Throwable) : ApiError
}

sealed interface ApiResult<out T> {
    data class Success<T>(val data: T, val meta: ApiMeta? = null) : ApiResult<T>
    data class Failure(val error: ApiError) : ApiResult<Nothing>
}

inline fun <T, R> ApiResult<T>.map(transform: (T) -> R): ApiResult<R> = when (this) {
    is ApiResult.Success -> ApiResult.Success(transform(data), meta)
    is ApiResult.Failure -> this
}
