package com.unefy.feature.documents

import com.unefy.core.database.SyncedMemberDao
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

/**
 * A document the club has issued, as it was issued.
 *
 * The body travels along and is never re-rendered from the template: the
 * template is free to change afterwards and may be gone entirely, and a
 * certificate that quietly says something else than when it was signed is
 * worse than no certificate. The app only displays it.
 */
data class IssuedDocument(
    val id: String,
    val memberId: String,
    val templateName: String,
    val title: String,
    val issuedAt: String,
    val revokedAt: String?,
    val revokeReason: String?,
    /** Only on a verifiable document — it is what the check page looks up. */
    val verificationCode: String?,
    val signedAt: String?,
) {
    val isRevoked: Boolean get() = revokedAt != null
}

/** A wording the club may issue from. Only the active ones are offered. */
data class DocumentTemplate(val id: String, val name: String, val title: String)

@Serializable
internal data class IssuedDocumentDto(
    val id: String,
    @SerialName("member_id") val memberId: String,
    @SerialName("template_name") val templateName: String,
    val title: String,
    @SerialName("issued_at") val issuedAt: String,
    @SerialName("revoked_at") val revokedAt: String? = null,
    @SerialName("revoke_reason") val revokeReason: String? = null,
    @SerialName("verification_code") val verificationCode: String? = null,
    @SerialName("signed_at") val signedAt: String? = null,
)

internal fun IssuedDocumentDto.toDomain() = IssuedDocument(
    id = id,
    memberId = memberId,
    templateName = templateName,
    title = title,
    issuedAt = issuedAt,
    revokedAt = revokedAt,
    revokeReason = revokeReason,
    verificationCode = verificationCode,
    signedAt = signedAt,
)

@Serializable
internal data class TemplateDto(
    val id: String,
    val name: String,
    val title: String,
)

@Serializable
internal data class IssuePayload(@SerialName("template_id") val templateId: String)

/** A member to issue to, from the local mirror rather than from the API. */
data class MemberPick(val id: String, val name: String, val memberNumber: String)

interface DocumentsRepository {

    /** What the club has issued to the signed-in member. Any role. */
    suspend fun myDocuments(): ApiResult<List<IssuedDocument>>

    /** Everything the club has issued, newest first. Board and above. */
    suspend fun allDocuments(): ApiResult<List<IssuedDocument>>

    /** The active wordings, for the issuing sheet. Board and above. */
    suspend fun templates(): ApiResult<List<DocumentTemplate>>

    /**
     * Issue a document for one member and freeze its text.
     *
     * Never queued, unlike a member edit. Issuing allocates a verification code
     * and a place in the club's record of what it has certified; a queued one
     * would be handed over as done while the club has no idea it exists, and
     * the check page would say the document is not real.
     */
    suspend fun issue(memberId: String, templateId: String): ApiResult<IssuedDocument>

    /**
     * The document as a PDF.
     *
     * [own] picks the route rather than the role: a member's own document has
     * its own endpoint, and asking the board's one as a member is a 403 no
     * matter whose document it is.
     */
    suspend fun pdf(documentId: String, own: Boolean): ApiResult<ByteArray>

    /**
     * Member id to display name, from the mirror.
     *
     * The API answers a document with a member id and nothing else, and a list
     * of twenty documents must not become twenty lookups. The mirror already
     * holds every member of the club, so the names are free and available
     * offline; an id the mirror has never seen simply has no name, which the
     * row states rather than papers over.
     */
    fun memberNames(): Flow<Map<String, String>>

    /** The members to pick from when issuing, filtered by the mirror's search. */
    fun members(query: String): Flow<List<MemberPick>>
}

@Singleton
class DefaultDocumentsRepository @Inject constructor(
    private val apiClient: ApiClient,
    private val members: SyncedMemberDao,
) : DocumentsRepository {

    override suspend fun myDocuments(): ApiResult<List<IssuedDocument>> = apiClient
        .get<List<IssuedDocumentDto>>(ApiEndpoints.DOCUMENTS_ME)
        .map { dtos -> dtos.map(IssuedDocumentDto::toDomain) }

    override suspend fun allDocuments(): ApiResult<List<IssuedDocument>> = apiClient
        .get<List<IssuedDocumentDto>>(ApiEndpoints.DOCUMENTS)
        .map { dtos -> dtos.map(IssuedDocumentDto::toDomain) }

    override suspend fun templates(): ApiResult<List<DocumentTemplate>> = apiClient
        .get<List<TemplateDto>>(ApiEndpoints.DOCUMENT_TEMPLATES) {
            // The default already excludes inactive ones; said out loud because
            // issuing from a retired wording is exactly what must not happen.
            parameter("include_inactive", false)
        }
        .map { dtos -> dtos.map { DocumentTemplate(it.id, it.name, it.title) } }

    override suspend fun issue(
        memberId: String,
        templateId: String,
    ): ApiResult<IssuedDocument> = apiClient
        .post<IssuedDocumentDto>(
            ApiEndpoints.issueDocument(memberId),
            body = IssuePayload(templateId),
        )
        .map(IssuedDocumentDto::toDomain)

    override suspend fun pdf(documentId: String, own: Boolean): ApiResult<ByteArray> =
        apiClient.getBytes(
            if (own) {
                ApiEndpoints.ownDocumentPdf(documentId)
            } else {
                ApiEndpoints.documentPdf(documentId)
            },
        )

    override fun memberNames(): Flow<Map<String, String>> = members.search("").map { rows ->
        rows.associate { it.id to "${it.firstName} ${it.lastName}".trim() }
    }

    override fun members(query: String): Flow<List<MemberPick>> = members.search(query).map { rows ->
        rows.map { MemberPick(it.id, "${it.firstName} ${it.lastName}".trim(), it.memberNumber) }
    }
}

@Module
@InstallIn(SingletonComponent::class)
abstract class DocumentsModule {
    @Binds
    abstract fun bindDocumentsRepository(impl: DefaultDocumentsRepository): DocumentsRepository
}
