package com.unefy.feature.documents

import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import java.io.IOException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class DocumentsViewModelTest {

    private val dispatcher = StandardTestDispatcher()

    @Before
    fun setUp() = Dispatchers.setMain(dispatcher)

    @After
    fun tearDown() = Dispatchers.resetMain()

    /**
     * The board's list is a 403 for a member and the member's own is the wrong
     * list for the board, so the role has to pick the request — not a filter
     * applied afterwards.
     */
    @Test
    fun `a member asks for their own documents, the board for the club's`() =
        runTest(dispatcher) {
            val mine = FakeDocumentsRepository()
            DocumentsViewModel(mine).load(board = false)
            advanceUntilIdle()
            assertEquals(listOf("me"), mine.calls)

            val all = FakeDocumentsRepository()
            DocumentsViewModel(all).load(board = true)
            advanceUntilIdle()
            assertEquals(listOf("all"), all.calls)
        }

    @Test
    fun `only the board is offered the issuing button`() = runTest(dispatcher) {
        val member = DocumentsViewModel(FakeDocumentsRepository())
        member.load(board = false)
        advanceUntilIdle()
        assertEquals(false, member.uiState.value.canIssue)

        val board = DocumentsViewModel(FakeDocumentsRepository())
        board.load(board = true)
        advanceUntilIdle()
        assertEquals(true, board.uiState.value.canIssue)
    }

    @Test
    fun `an issued document joins the list and closes the sheet`() = runTest(dispatcher) {
        val repository = FakeDocumentsRepository()
        val viewModel = DocumentsViewModel(repository)
        viewModel.load(board = true)
        advanceUntilIdle()

        viewModel.startIssue()
        advanceUntilIdle()
        viewModel.pickMember(MemberPick("m9", "Nina Roth", "0099"))
        viewModel.issue("t1")
        advanceUntilIdle()

        val state = viewModel.uiState.value
        assertNull(state.issue)
        assertEquals(listOf("new", "1"), state.documents.map { it.id })
        assertEquals(DocumentNotice.Issued, state.notice)
        assertEquals(listOf("m9" to "t1"), repository.issued)
    }

    /**
     * A document is the club certifying something, and it carries a code
     * somebody may look up. A row that appeared before the server agreed would
     * be a certificate the check page calls fake.
     */
    @Test
    fun `an issue that failed adds nothing and leaves the sheet open`() = runTest(dispatcher) {
        val repository = FakeDocumentsRepository()
        repository.issueResult = ApiResult.Failure(ApiError.Network(IOException("offline")))
        val viewModel = DocumentsViewModel(repository)
        viewModel.load(board = true)
        advanceUntilIdle()

        viewModel.startIssue()
        advanceUntilIdle()
        viewModel.pickMember(MemberPick("m9", "Nina Roth", "0099"))
        viewModel.issue("t1")
        advanceUntilIdle()

        val state = viewModel.uiState.value
        assertNotNull(state.issue)
        // Not stuck working: the button has to be usable for a second attempt.
        assertEquals(false, state.issue?.working)
        assertEquals(listOf("1"), state.documents.map { it.id })
        assertEquals(DocumentNotice.Failed, state.notice)
    }

    /**
     * An empty picker would read as "no wordings match", which is a different
     * problem from "the club has not written any" — and only one of the two has
     * an answer the board member can act on.
     */
    @Test
    fun `a club with no wording is told so instead of getting an empty sheet`() =
        runTest(dispatcher) {
            val repository = FakeDocumentsRepository()
            repository.templates = ApiResult.Success(emptyList())
            val viewModel = DocumentsViewModel(repository)
            viewModel.load(board = true)
            advanceUntilIdle()

            viewModel.startIssue()
            advanceUntilIdle()

            assertNull(viewModel.uiState.value.issue)
            assertEquals(DocumentNotice.NoTemplates, viewModel.uiState.value.notice)
        }

    /** A refresh that fails must not empty a list that is already on screen. */
    @Test
    fun `a failed refresh keeps the documents it already had`() = runTest(dispatcher) {
        val repository = FakeDocumentsRepository()
        val viewModel = DocumentsViewModel(repository)
        viewModel.load(board = true)
        advanceUntilIdle()

        repository.listResult = ApiResult.Failure(ApiError.Network(IOException("offline")))
        viewModel.refresh()
        advanceUntilIdle()

        val state = viewModel.uiState.value
        assertEquals(listOf("1"), state.documents.map { it.id })
        assertTrue(state.error is ApiError.Network)
    }
}

private fun document(id: String) = IssuedDocument(
    id = id,
    memberId = "m1",
    templateName = "Mitgliedsbescheinigung",
    title = "Mitgliedsbescheinigung",
    issuedAt = "2026-08-11T10:00:00Z",
    revokedAt = null,
    revokeReason = null,
    verificationCode = "ABCD-1234",
    signedAt = null,
)

private class FakeDocumentsRepository : DocumentsRepository {

    /** Which list was asked for — the whole point of the role split. */
    val calls = mutableListOf<String>()
    val issued = mutableListOf<Pair<String, String>>()

    var listResult: ApiResult<List<IssuedDocument>> = ApiResult.Success(listOf(document("1")))
    var templates: ApiResult<List<DocumentTemplate>> =
        ApiResult.Success(listOf(DocumentTemplate("t1", "Mitgliedsbescheinigung", "Bescheinigung")))
    var issueResult: ApiResult<IssuedDocument> = ApiResult.Success(document("new"))

    override suspend fun myDocuments(): ApiResult<List<IssuedDocument>> {
        calls += "me"
        return listResult
    }

    override suspend fun allDocuments(): ApiResult<List<IssuedDocument>> {
        calls += "all"
        return listResult
    }

    override suspend fun templates(): ApiResult<List<DocumentTemplate>> = templates

    override suspend fun issue(memberId: String, templateId: String): ApiResult<IssuedDocument> {
        issued += memberId to templateId
        return issueResult
    }

    override suspend fun pdf(documentId: String, own: Boolean): ApiResult<ByteArray> =
        error("not used")

    override fun memberNames(): Flow<Map<String, String>> = flowOf(mapOf("m1" to "Susanne Bauer"))

    override fun members(query: String): Flow<List<MemberPick>> = flowOf(emptyList())
}
