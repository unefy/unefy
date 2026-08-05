package com.unefy.feature.members

import com.unefy.core.model.DirectoryEntry
import com.unefy.core.model.Member
import com.unefy.core.model.MemberStatus
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import com.unefy.core.sync.SyncCoordinator
import com.unefy.core.sync.SyncStatus
import com.unefy.core.testing.FakeCoordinator
import java.io.IOException
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
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * The member list reads a local mirror now rather than fetching a page.
 *
 * What that changes, and what these tests pin: the list is a query over rows that
 * are already there, so "loading" means the mirror has never been filled, an empty
 * list means the club is empty, and a sync failure is a banner over real data
 * rather than a screen full of error. Confusing the first two is how a first launch
 * ends up claiming the club has no members while the bootstrap is still running.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class MembersViewModelTest {

    private val dispatcher = StandardTestDispatcher()

    @Before
    fun setUp() = Dispatchers.setMain(dispatcher)

    @After
    fun tearDown() = Dispatchers.resetMain()

    @Test
    fun `an unsynced mirror is Loading, not empty`() = runTest(dispatcher) {
        val viewModel = viewModel(FakeMembersRepository(hasSynced = false))
        advanceUntilIdle()

        assertEquals(MembersUiState.Loading, viewModel.uiState.value)
    }

    /**
     * The distinction the stored cursor exists for. Same zero rows as above,
     * opposite meaning — and the only thing telling them apart is whether a sync
     * has ever finished.
     */
    @Test
    fun `a synced but empty mirror is Content, not Loading`() = runTest(dispatcher) {
        val viewModel = viewModel(FakeMembersRepository(members = emptyList(), hasSynced = true))
        advanceUntilIdle()

        val state = viewModel.uiState.value
        assertTrue(state is MembersUiState.Content)
        assertEquals(emptyList<Member>(), (state as MembersUiState.Content).members)
    }

    @Test
    fun `mirrored members are shown with the club's total`() = runTest(dispatcher) {
        val viewModel = viewModel(
            FakeMembersRepository(members = listOf(member("1"), member("2")), total = 47),
        )
        advanceUntilIdle()

        val state = viewModel.uiState.value as MembersUiState.Content
        assertEquals(listOf("1", "2"), state.members.map(Member::id))
        // The club's size, not the number of rows on screen.
        assertEquals(47, state.total)
    }

    /**
     * The point of the mirror: a change synced in the background reaches the screen
     * without the screen asking for anything.
     */
    @Test
    fun `a row appearing in the mirror reaches the screen unasked`() = runTest(dispatcher) {
        val repository = FakeMembersRepository(members = listOf(member("1")))
        val viewModel = viewModel(repository)
        advanceUntilIdle()

        repository.rows.value = listOf(member("1"), member("2"))
        advanceUntilIdle()

        val state = viewModel.uiState.value as MembersUiState.Content
        assertEquals(listOf("1", "2"), state.members.map(Member::id))
    }

    @Test
    fun `a query filters against the mirror`() = runTest(dispatcher) {
        val viewModel = viewModel(
            FakeMembersRepository(
                members = listOf(member("1", last = "Müller"), member("2", last = "Bauer")),
            ),
        )
        advanceUntilIdle()

        viewModel.onQueryChange("müller")
        advanceUntilIdle()

        val state = viewModel.uiState.value as MembersUiState.Content
        assertEquals(listOf("1"), state.members.map(Member::id))
        assertEquals("müller", state.query)
    }

    /**
     * Query and results have to move together. Combining them from separate flows
     * lets a keystroke pair the new query with the old list for a frame, which is
     * long enough to render "no matches" over results that do match.
     */
    @Test
    fun `the query on screen always matches the list on screen`() = runTest(dispatcher) {
        val viewModel = viewModel(
            FakeMembersRepository(
                members = listOf(member("1", last = "Müller"), member("2", last = "Bauer")),
            ),
        )
        advanceUntilIdle()

        viewModel.onQueryChange("bauer")
        advanceUntilIdle()

        val state = viewModel.uiState.value as MembersUiState.Content
        assertEquals("bauer", state.query)
        assertEquals(listOf("2"), state.members.map(Member::id))
    }

    /**
     * A failed sync over a mirror that holds data is a banner, not a takeover.
     * Replacing a working list with a full-screen error because the connection
     * dropped for a second is worse than showing a list a minute out of date.
     */
    @Test
    fun `a sync failure keeps the list and reports why it is stale`() = runTest(dispatcher) {
        val coordinator = FakeCoordinator()
        val viewModel = viewModel(FakeMembersRepository(members = listOf(member("1"))), coordinator)
        advanceUntilIdle()

        coordinator.status.value = SyncStatus.Failed(ApiError.Network(IOException("no signal")))
        advanceUntilIdle()

        val state = viewModel.uiState.value as MembersUiState.Content
        assertEquals(listOf("1"), state.members.map(Member::id))
        assertTrue(state.staleBecause is ApiError.Network)
    }

    /** It clears itself: there is no event to dismiss, only a fact that stops being true. */
    @Test
    fun `a later successful sync clears the stale reason`() = runTest(dispatcher) {
        val coordinator = FakeCoordinator(SyncStatus.Failed(ApiError.Network(IOException())))
        val viewModel = viewModel(FakeMembersRepository(members = listOf(member("1"))), coordinator)
        advanceUntilIdle()
        assertTrue((viewModel.uiState.value as MembersUiState.Content).staleBecause != null)

        coordinator.status.value = SyncStatus.Idle
        advanceUntilIdle()

        assertNull((viewModel.uiState.value as MembersUiState.Content).staleBecause)
    }

    /** With nothing mirrored there is no list to keep, so the error is all there is. */
    @Test
    fun `a sync failure with an empty mirror is a Failure`() = runTest(dispatcher) {
        val coordinator = FakeCoordinator(SyncStatus.Failed(ApiError.Network(IOException())))
        val viewModel = viewModel(FakeMembersRepository(hasSynced = false), coordinator)
        advanceUntilIdle()

        val state = viewModel.uiState.value
        assertTrue(state is MembersUiState.Failure)
        assertTrue((state as MembersUiState.Failure).error is ApiError.Network)
    }

    /**
     * A plain member may not mirror the member list. Reported as Forbidden because
     * that is what it is, and because signing in again will not help.
     */
    @Test
    fun `a refused collection is a Forbidden failure`() = runTest(dispatcher) {
        val coordinator = FakeCoordinator(SyncStatus.NotPermitted)
        val viewModel = viewModel(FakeMembersRepository(hasSynced = false), coordinator)
        advanceUntilIdle()

        assertEquals(MembersUiState.Failure(ApiError.Forbidden), viewModel.uiState.value)
    }

    @Test
    fun `refresh asks the coordinator to sync now`() = runTest(dispatcher) {
        val coordinator = FakeCoordinator()
        val viewModel = viewModel(FakeMembersRepository(), coordinator)
        advanceUntilIdle()

        viewModel.refresh()
        advanceUntilIdle()

        assertEquals(listOf("members"), coordinator.syncedNow)
    }

    /**
     * The pull gesture fires on drag rather than on intent, so a slow sync would
     * otherwise be asked for several times over.
     */
    @Test
    fun `a second refresh while one is running is ignored`() = runTest(dispatcher) {
        val coordinator = FakeCoordinator(blockSync = true)
        val viewModel = viewModel(FakeMembersRepository(), coordinator)
        advanceUntilIdle()

        viewModel.refresh()
        viewModel.refresh()
        viewModel.refresh()
        advanceUntilIdle()

        assertEquals(1, coordinator.syncedNow.size)
    }

    /**
     * Builds the ViewModel and subscribes to its state.
     *
     * The subscription is not incidental. `uiState` is shared with
     * `WhileSubscribed`, so with no collector it never runs its upstream and
     * reports its initial value forever — which in a test looks exactly like a
     * ViewModel stuck on Loading. Compose provides the collector in the app; here
     * `backgroundScope` does, and it is torn down with the test.
     */
    private fun TestScope.viewModel(
        repository: MembersRepository,
        coordinator: SyncCoordinator = FakeCoordinator(),
    ) = MembersViewModel(repository, coordinator).also { vm ->
        backgroundScope.launch { vm.uiState.collect {} }
    }
}

private fun member(id: String, last: String = "Muster") = Member(
    id = id,
    memberNumber = "000$id",
    firstName = "Vorname",
    lastName = last,
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

/**
 * Stands in for Room. [rows] is mutable so a test can change the mirror under the
 * screen, which is the behaviour the whole rewrite is for.
 *
 * The filter is the same shape as the DAO's — a case-insensitive substring over the
 * name — but not the same code. What the real SQL does with umlauts is tested
 * against real SQLite in `SyncedMemberDaoTest`.
 */
private class FakeMembersRepository(
    members: List<Member> = emptyList(),
    private val total: Int? = null,
    private val hasSynced: Boolean = true,
) : MembersRepository {

    val rows = MutableStateFlow(members)

    override fun stream(query: String): Flow<List<Member>> = rows.map { list ->
        if (query.isBlank()) {
            list
        } else {
            list.filter { it.displayName.contains(query, ignoreCase = true) }
        }
    }

    override fun count(): Flow<Int> = rows.map { total ?: it.size }

    override fun hasSynced(): Flow<Boolean> = MutableStateFlow(hasSynced)

    override fun byIdStream(id: String): Flow<Member?> = rows.map { list ->
        list.firstOrNull { it.id == id }
    }

    override suspend fun byId(id: String): ApiResult<Member> =
        rows.value.firstOrNull { it.id == id }
            ?.let { ApiResult.Success(it) }
            ?: ApiResult.Failure(ApiError.NotFound(null))

    override suspend fun federations(id: String): ApiResult<List<FederationMembership>> =
        ApiResult.Success(emptyList())

    override suspend fun me(): ApiResult<Member> =
        rows.value.firstOrNull()?.let { ApiResult.Success(it) }
            ?: ApiResult.Failure(ApiError.NotFound(null))

    override suspend fun directory(
        page: Int,
        perPage: Int,
        search: String?,
    ): ApiResult<List<DirectoryEntry>> = ApiResult.Success(emptyList())
}
