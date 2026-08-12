package com.unefy.core.network

import io.ktor.client.HttpClient
import io.ktor.client.call.body
import io.ktor.client.request.HttpRequestBuilder
import io.ktor.client.request.delete
import io.ktor.client.request.get
import io.ktor.client.request.patch
import io.ktor.client.request.post
import io.ktor.client.request.setBody
import io.ktor.client.statement.HttpResponse
import io.ktor.http.ContentType
import io.ktor.http.contentType
import io.ktor.http.isSuccess
import java.io.IOException
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.serialization.SerializationException

/**
 * Thin wrapper over the Ktor client that turns every call into an [ApiResult].
 *
 * Nothing above this class sees an exception, an HTTP status or a raw response
 * body — repositories get typed data or a typed error. Token refresh happens
 * below this layer, inside the Ktor Auth plugin.
 */
@Singleton
class ApiClient @Inject constructor(
    // @PublishedApi: the reified helpers below are inline, so they cannot touch
    // private members.
    @PublishedApi internal val httpClient: HttpClient,
) {
    suspend inline fun <reified T> get(
        path: String,
        crossinline block: HttpRequestBuilder.() -> Unit = {},
    ): ApiResult<T> = execute { httpClient.get(path) { block() } }

    suspend inline fun <reified T> post(
        path: String,
        body: Any? = null,
        crossinline block: HttpRequestBuilder.() -> Unit = {},
    ): ApiResult<T> = execute {
        httpClient.post(path) {
            contentType(ContentType.Application.Json)
            if (body != null) setBody(body)
            block()
        }
    }

    /**
     * The first PATCH in the app, for a partial update.
     *
     * Separate from [post] rather than a verb parameter: the two differ in what
     * they mean, not only in a string. A POST creates and repeating it creates
     * again; a PATCH sets the fields it names and repeating it is harmless. Only
     * one of them may be retried without asking.
     */
    suspend inline fun <reified T> patch(
        path: String,
        body: Any? = null,
        crossinline block: HttpRequestBuilder.() -> Unit = {},
    ): ApiResult<T> = execute {
        httpClient.patch(path) {
            contentType(ContentType.Application.Json)
            if (body != null) setBody(body)
            block()
        }
    }

    /**
     * For endpoints that put metadata beside `data` instead of inside `meta` —
     * the scoreboard carries `scoring_unit` and `scoring_mode` at the top level.
     * The caller's type models the whole body, envelope included, because
     * decoding it as [ApiEnvelope] would silently drop those fields.
     */
    suspend inline fun <reified T> getWhole(
        path: String,
        crossinline block: HttpRequestBuilder.() -> Unit = {},
    ): ApiResult<T> = try {
        val response = httpClient.get(path) { block() }
        if (response.status.isSuccess()) {
            ApiResult.Success(response.body())
        } else {
            val body = runCatching { response.body<ApiEnvelope<Unit>>().error }.getOrNull()
            ApiResult.Failure(errorFor(response.status.value, body))
        }
    } catch (e: SerializationException) {
        ApiResult.Failure(ApiError.Serialization(e))
    } catch (e: IOException) {
        ApiResult.Failure(ApiError.Network(e))
    } catch (
        @Suppress("TooGenericExceptionCaught") e: Exception,
    ) {
        ApiResult.Failure(ApiError.Unknown(e))
    }

    /**
     * The whole body as bytes, for endpoints that answer with a file.
     *
     * Not generic and not an envelope: a PDF is the response, not a field
     * inside one. Errors still arrive as the usual envelope, so a failure is
     * decoded the same way as everywhere else and the caller keeps working in
     * [ApiError] rather than in status codes.
     *
     * Loaded whole rather than streamed. A club document is one or two pages;
     * the alternative is a handle whose lifetime the caller has to manage, and
     * nothing here needs that yet.
     */
    suspend fun getBytes(path: String): ApiResult<ByteArray> = try {
        val response = httpClient.get(path)
        if (response.status.isSuccess()) {
            ApiResult.Success(response.body<ByteArray>())
        } else {
            val body = runCatching { response.body<ApiEnvelope<Unit>>().error }.getOrNull()
            ApiResult.Failure(errorFor(response.status.value, body))
        }
    } catch (e: IOException) {
        ApiResult.Failure(ApiError.Network(e))
    } catch (
        @Suppress("TooGenericExceptionCaught") e: Exception,
    ) {
        ApiResult.Failure(ApiError.Unknown(e))
    }

    /**
     * For endpoints that answer 204 with no body. Not inline and not generic:
     * there is nothing to decode, and calling [execute] here would try to parse
     * an envelope that was never sent.
     */
    suspend fun deleteNoContent(path: String): ApiResult<Unit> =
        noContent { httpClient.delete(path) }

    /** [deleteNoContent]'s sibling for 204-answering POSTs with a JSON body. */
    suspend fun postNoContent(path: String, body: Any): ApiResult<Unit> = noContent {
        httpClient.post(path) {
            contentType(ContentType.Application.Json)
            setBody(body)
        }
    }

    private suspend fun noContent(request: suspend () -> HttpResponse): ApiResult<Unit> = try {
        val response = request()
        if (response.status.isSuccess()) {
            ApiResult.Success(Unit)
        } else {
            val body = runCatching { response.body<ApiEnvelope<Unit>>().error }.getOrNull()
            ApiResult.Failure(errorFor(response.status.value, body))
        }
    } catch (e: IOException) {
        ApiResult.Failure(ApiError.Network(e))
    } catch (
        @Suppress("TooGenericExceptionCaught") e: Exception,
    ) {
        ApiResult.Failure(ApiError.Unknown(e))
    }

    @PublishedApi
    internal suspend inline fun <reified T> execute(request: () -> HttpResponse): ApiResult<T> = try {
        val response = request()
        val envelope: ApiEnvelope<T> = response.body()

        when {
            response.status.isSuccess() && envelope.data != null ->
                ApiResult.Success(envelope.data, envelope.meta)

            response.status.isSuccess() ->
                ApiResult.Failure(
                    ApiError.Serialization(IllegalStateException("2xx response without data")),
                )

            else -> ApiResult.Failure(errorFor(response.status.value, envelope.error))
        }
    } catch (e: SerializationException) {
        ApiResult.Failure(ApiError.Serialization(e))
    } catch (e: IOException) {
        ApiResult.Failure(ApiError.Network(e))
    } catch (
        @Suppress("TooGenericExceptionCaught") e: Exception,
    ) {
        ApiResult.Failure(ApiError.Unknown(e))
    }

    @PublishedApi
    internal fun errorFor(status: Int, body: ApiErrorBody?): ApiError = when (status) {
        401 -> ApiError.Unauthorized
        403 -> ApiError.Forbidden
        404 -> ApiError.NotFound(body?.code)
        else -> ApiError.Http(status, body?.code, body?.message)
    }
}
