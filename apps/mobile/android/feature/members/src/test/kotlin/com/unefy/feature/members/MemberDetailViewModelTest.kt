package com.unefy.feature.members

import com.unefy.core.model.DirectoryEntry
import com.unefy.core.model.Member
import com.unefy.core.model.MemberStatus
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import java.io.IOException
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * The detail screen's third source. Mirror and one-shot fetch are pinned by the
 * screen's own design comment; what these tests add is the federations list —
 * server-only, and deliberately without an error state of its own.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class MemberDetailViewModelTest {

    private val dispatcher = StandardTestDispatcher()

    @Before
    fun setUp() = Dispatchers.setMain(dispatcher)

    @After
    fun tearDown() = Dispatchers.resetMain()

    @Test
    fun `federation memberships arrive alongside the member`() = runTest(dispatcher) {
        val federation = FederationMembership(
            id = "f1",
            federation = "WSV/DSB",
            federationNumber = "84839114",
            joinedAt = "2008-08-01",
            leftAt = null,
        )
        val viewModel = viewModel(
            FakeDetailRepository(
                members = listOf(member("1")),
                federations = ApiResult.Success(listOf(federation)),
            ),
        )
        viewModel.load("1")
        advanceUntilIdle()

        val state = viewModel.uiState.value
        assertTrue(state is MemberDetailUiState.Content)
        assertEquals(listOf(federation), (state as MemberDetailUiState.Content).federations)
    }

    /**
     * A plain member gets 403 from the endpoint, and offline gets a network
     * error — both must degrade to "no section", never to a failed screen over
     * a member the mirror can perfectly well show.
     */
    @Test
    fun `a failed federations fetch leaves the member intact`() = runTest(dispatcher) {
        val viewModel = viewModel(
            FakeDetailRepository(
                members = listOf(member("1")),
                federations = ApiResult.Failure(ApiError.Forbidden),
            ),
        )
        viewModel.load("1")
        advanceUntilIdle()

        val state = viewModel.uiState.value
        assertTrue(state is MemberDetailUiState.Content)
        state as MemberDetailUiState.Content
        assertEquals("1", state.member.id)
        assertEquals(emptyList<FederationMembership>(), state.federations)
    }

    @Test
    fun `terms of office arrive alongside the member`() = runTest(dispatcher) {
        val viewModel = viewModel(
            FakeDetailRepository(
                members = listOf(member("1")),
                functions = ApiResult.Success(listOf(office("o1"), office("o2", validTo = null))),
            ),
        )
        viewModel.load("1")
        advanceUntilIdle()

        val state = viewModel.uiState.value as MemberDetailUiState.Content
        assertEquals(listOf("o1", "o2"), state.functions.map { it.id })
    }

    /**
     * The same degradation as the federations above: a plain member gets 403
     * here and an offline phone gets nothing, and neither may turn a member the
     * mirror can show perfectly well into an error screen.
     */
    @Test
    fun `a failed office fetch leaves the member intact`() = runTest(dispatcher) {
        val viewModel = viewModel(
            FakeDetailRepository(
                members = listOf(member("1")),
                functions = ApiResult.Failure(ApiError.Forbidden),
            ),
        )
        viewModel.load("1")
        advanceUntilIdle()

        val state = viewModel.uiState.value as MemberDetailUiState.Content
        assertEquals("1", state.member.id)
        assertEquals(emptyList<OfficeTerm>(), state.functions)
    }

    /**
     * Opening a second member must not show the first one's offices. The
     * ViewModel is per-entry, but `load` is also called again on a
     * configuration change, and the lists are cleared there for that reason.
     */
    @Test
    fun `switching member drops the previous offices`() = runTest(dispatcher) {
        val repository = FakeDetailRepository(
            members = listOf(member("1"), member("2")),
            functions = ApiResult.Success(listOf(office("o1"))),
        )
        val viewModel = viewModel(repository)
        viewModel.load("1")
        advanceUntilIdle()
        assertEquals(1, content(viewModel).functions.size)

        repository.functionsResult = ApiResult.Failure(ApiError.Forbidden)
        viewModel.load("2")
        advanceUntilIdle()

        assertEquals(emptyList<OfficeTerm>(), content(viewModel).functions)
    }

    /**
     * Revoking is the only answer to a lost phone that does not mean waiting
     * three days for the grace window to run out.
     */
    @Test
    fun `revoking reports success only once the server has answered`() = runTest {
        val repository = FakeDetailRepository(listOf(member("1")))
        val viewModel = viewModel(repository)
        viewModel.load("1")
        runCurrent()

        viewModel.revokeCodes()
        runCurrent()

        assertEquals(1, repository.revokeCalls)
        assertEquals(RevokeState.Done, content(viewModel).revoke)
    }

    /**
     * Deliberately not queued, and therefore deliberately not dressed up: a
     * revocation that looked successful while sitting in a queue would leave
     * the lost phone working with nobody looking.
     */
    @Test
    fun `a revocation that cannot reach the server says so`() = runTest {
        val repository = FakeDetailRepository(listOf(member("1")))
        repository.revokeResult = ApiResult.Failure(ApiError.Network(IOException("offline")))
        val viewModel = viewModel(repository)
        viewModel.load("1")
        runCurrent()

        viewModel.revokeCodes()
        runCurrent()

        assertEquals(RevokeState.Failed, content(viewModel).revoke)
    }

    private fun content(viewModel: MemberDetailViewModel) =
        viewModel.uiState.value as MemberDetailUiState.Content

    /** See MembersViewModelTest — WhileSubscribed needs a live collector. */
    private fun TestScope.viewModel(repository: MembersRepository): MemberDetailViewModel {
        val viewModel = MemberDetailViewModel(repository)
        backgroundScope.launch { viewModel.uiState.collect {} }
        return viewModel
    }
}

private fun member(id: String) = Member(
    id = id,
    memberNumber = "000$id",
    firstName = "Vorname",
    lastName = "Muster",
    email = null,
    phone = null,
    mobile = null,
    birthday = null,
    gender = null,
    street = null,
    zipCode = null,
    city = null,
    status = MemberStatus.ACTIVE,
    category = null,
    joinedAt = "2007-04-10",
    leftAt = null,
    iban = null,
)

private fun office(
    id: String,
    validFrom: String = "2024-03-01",
    validTo: String? = null,
) = OfficeTerm(
    id = id,
    functionName = "Kassenwart",
    level = "club",
    divisionName = null,
    validFrom = validFrom,
    validTo = validTo,
    note = null,
)

private class FakeDetailRepository(
    members: List<Member> = emptyList(),
    private val federations: ApiResult<List<FederationMembership>> =
        ApiResult.Success(emptyList()),
    functions: ApiResult<List<OfficeTerm>> = ApiResult.Success(emptyList()),
) : MembersRepository {

    /** A var, so a test can change the answer between two `load` calls. */
    var functionsResult: ApiResult<List<OfficeTerm>> = functions

    private val rows = MutableStateFlow(members)

    override fun stream(query: String): Flow<List<Member>> = rows

    override fun count(): Flow<Int> = rows.map { it.size }

    override fun hasSynced(): Flow<Boolean> = MutableStateFlow(true)

    override fun byIdStream(id: String): Flow<Member?> = rows.map { list ->
        list.firstOrNull { it.id == id }
    }

    override suspend fun byId(id: String): ApiResult<Member> =
        rows.value.firstOrNull { it.id == id }
            ?.let { ApiResult.Success(it) }
            ?: ApiResult.Failure(ApiError.NotFound(null))

    override suspend fun federations(id: String): ApiResult<List<FederationMembership>> =
        federations

    override suspend fun functions(id: String): ApiResult<List<OfficeTerm>> = functionsResult

    override suspend fun myFunctions(): ApiResult<List<OfficeTerm>> = functionsResult

    override suspend fun me(): ApiResult<Member> =
        ApiResult.Failure(ApiError.NotFound(null))

    override suspend fun directory(
        page: Int,
        perPage: Int,
        search: String?,
    ): ApiResult<List<DirectoryEntry>> = ApiResult.Success(emptyList())

    override suspend fun save(id: String?, draft: MemberDraft): String = id ?: "new-id"

    override fun pendingIds(): Flow<Set<String>> = MutableStateFlow(emptySet())

    override suspend fun discardPending(id: String) = Unit

    /** Counted and steerable: the revocation must reach the server, and must
     *  say so when it did not. */
    var revokeCalls = 0
    var revokeResult: ApiResult<Unit> = ApiResult.Success(Unit)

    override suspend fun revokeAttendanceCodes(id: String): ApiResult<Unit> {
        revokeCalls++
        return revokeResult
    }
}
