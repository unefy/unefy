package com.unefy.feature.members

import com.unefy.core.model.DirectoryEntry
import com.unefy.core.model.Member
import com.unefy.core.model.MemberStatus
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
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

private class FakeDetailRepository(
    members: List<Member> = emptyList(),
    private val federations: ApiResult<List<FederationMembership>> =
        ApiResult.Success(emptyList()),
) : MembersRepository {

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
}
