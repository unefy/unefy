package com.unefy.feature.members

import com.unefy.core.model.DirectoryEntry
import com.unefy.core.model.Member
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
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test

/**
 * The one screen in the app where an optimistic update would be a lie with
 * consequences: a withdrawal that shows as done but never left the phone means
 * the club goes on sending the newsletter while the member believes they
 * stopped it. These tests pin that the switch follows the server, not the tap.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class MyConsentsViewModelTest {

    private val dispatcher = StandardTestDispatcher()

    @Before
    fun setUp() = Dispatchers.setMain(dispatcher)

    @After
    fun tearDown() = Dispatchers.resetMain()

    @Test
    fun `a recorded answer becomes the current one and joins the trail`() = runTest(dispatcher) {
        val repository = FakeConsentRepository()
        val viewModel = MyConsentsViewModel(repository)
        advanceUntilIdle()

        viewModel.set("newsletter", granted = true)
        advanceUntilIdle()

        val overview = requireNotNull(viewModel.uiState.value.overview)
        val newsletter = overview.current.single { it.kind == "newsletter" }
        assertEquals(true, newsletter.granted)
        assertEquals("self", newsletter.source)
        // Newest first, and the earlier entries are still there: the ledger is
        // appended to, never rewritten.
        assertEquals(listOf("new", "old"), overview.history.map { it.id })
        assertEquals(ConsentNotice.Granted, viewModel.uiState.value.notice)
    }

    @Test
    fun `a write that never reached the server leaves the answer alone`() = runTest(dispatcher) {
        val repository = FakeConsentRepository()
        repository.result = ApiResult.Failure(ApiError.Network(IOException("offline")))
        val viewModel = MyConsentsViewModel(repository)
        advanceUntilIdle()

        viewModel.set("photos", granted = false)
        advanceUntilIdle()

        val overview = requireNotNull(viewModel.uiState.value.overview)
        // Still granted, and still since the same day: nothing was recorded, so
        // nothing may look recorded.
        assertEquals(true, overview.current.single { it.kind == "photos" }.granted)
        assertEquals(listOf("old"), overview.history.map { it.id })
        assertEquals(ConsentNotice.Failed, viewModel.uiState.value.notice)
        assertNull(viewModel.uiState.value.saving)
    }

    /**
     * Two answers in flight at once would land in the ledger in whichever order
     * the network chose, and the ledger is the proof.
     */
    @Test
    fun `a second answer while one is in flight is ignored`() = runTest(dispatcher) {
        val repository = FakeConsentRepository()
        val viewModel = MyConsentsViewModel(repository)
        advanceUntilIdle()

        viewModel.set("newsletter", granted = true)
        viewModel.set("directory", granted = true)
        advanceUntilIdle()

        assertEquals(listOf("newsletter" to true), repository.written)
    }

    /** Never asked is not a no, and must survive a round trip as null. */
    @Test
    fun `a kind nobody was asked about stays unanswered`() = runTest(dispatcher) {
        val viewModel = MyConsentsViewModel(FakeConsentRepository())
        advanceUntilIdle()

        val overview = requireNotNull(viewModel.uiState.value.overview)
        assertNull(overview.current.single { it.kind == "directory" }.granted)
    }
}

private class FakeConsentRepository : MembersRepository {

    val written = mutableListOf<Pair<String, Boolean>>()

    /** What the next write answers. A var so a test can make it fail. */
    var result: ApiResult<ConsentEntry> = ApiResult.Success(
        ConsentEntry(
            id = "new",
            kind = "newsletter",
            granted = true,
            recordedAt = "2026-08-12T10:00:00Z",
            source = "self",
            note = null,
        ),
    )

    override suspend fun myConsents(): ApiResult<ConsentOverview> = ApiResult.Success(
        ConsentOverview(
            current = listOf(
                ConsentState("photos", true, "2026-01-05T09:00:00Z", "board"),
                ConsentState("newsletter", false, "2026-01-05T09:00:00Z", "board"),
                ConsentState("directory", null, null, null),
            ),
            history = listOf(
                ConsentEntry(
                    id = "old",
                    kind = "photos",
                    granted = true,
                    recordedAt = "2026-01-05T09:00:00Z",
                    source = "board",
                    note = null,
                ),
            ),
        ),
    )

    override suspend fun recordConsent(kind: String, granted: Boolean): ApiResult<ConsentEntry> {
        written += kind to granted
        return result
    }

    override fun stream(query: String): Flow<List<Member>> = flowOf(emptyList())
    override fun count(): Flow<Int> = flowOf(0)
    override fun hasSynced(): Flow<Boolean> = flowOf(true)
    override fun byIdStream(id: String): Flow<Member?> = flowOf(null)
    override suspend fun byId(id: String): ApiResult<Member> = error("not used")
    override suspend fun federations(id: String): ApiResult<List<FederationMembership>> =
        error("not used")

    override suspend fun functions(id: String): ApiResult<List<OfficeTerm>> = error("not used")
    override suspend fun myFunctions(): ApiResult<List<OfficeTerm>> = error("not used")
    override suspend fun me(): ApiResult<Member> = error("not used")
    override suspend fun directory(
        page: Int,
        perPage: Int,
        search: String?,
    ): ApiResult<List<DirectoryEntry>> = error("not used")

    override suspend fun save(id: String?, draft: MemberDraft): String = error("not used")
    override fun pendingIds(): Flow<Set<String>> = flowOf(emptySet())
    override suspend fun discardPending(id: String) = Unit
    override suspend fun revokeAttendanceCodes(id: String): ApiResult<Unit> = error("not used")
}
