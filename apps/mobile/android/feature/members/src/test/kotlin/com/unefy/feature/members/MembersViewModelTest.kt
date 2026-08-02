package com.unefy.feature.members

import com.unefy.core.model.Member
import com.unefy.core.model.MemberStatus
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiMeta
import com.unefy.core.network.ApiResult
import java.io.IOException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class MembersViewModelTest {

    private val dispatcher = StandardTestDispatcher()

    @Before
    fun setUp() = Dispatchers.setMain(dispatcher)

    @After
    fun tearDown() = Dispatchers.resetMain()

    @Test
    fun `starts in Loading before the repository answers`() = runTest(dispatcher) {
        val viewModel = MembersViewModel(FakeMembersRepository())
        assertEquals(MembersUiState.Loading, viewModel.uiState.value)
    }

    @Test
    fun `successful load produces Content with the members`() = runTest(dispatcher) {
        val viewModel = MembersViewModel(FakeMembersRepository(members = listOf(member("1"))))
        advanceUntilIdle()

        val state = viewModel.uiState.value
        assertTrue(state is MembersUiState.Content)
        assertEquals(1, (state as MembersUiState.Content).members.size)
    }

    @Test
    fun `an empty club is Content, not an error`() = runTest(dispatcher) {
        val viewModel = MembersViewModel(FakeMembersRepository(members = emptyList()))
        advanceUntilIdle()

        assertEquals(MembersUiState.Content(emptyList()), viewModel.uiState.value)
    }

    @Test
    fun `a failing load surfaces the typed error`() = runTest(dispatcher) {
        val failure = ApiError.Network(IOException("offline"))
        val viewModel = MembersViewModel(FakeMembersRepository(failure = failure))
        advanceUntilIdle()

        assertEquals(MembersUiState.Failure(failure), viewModel.uiState.value)
    }

    @Test
    fun `retry after a failure recovers`() = runTest(dispatcher) {
        val repository = FakeMembersRepository(failure = ApiError.Unauthorized)
        val viewModel = MembersViewModel(repository)
        advanceUntilIdle()
        assertTrue(viewModel.uiState.value is MembersUiState.Failure)

        repository.failure = null
        repository.members = listOf(member("1"), member("2"))
        viewModel.retry()
        advanceUntilIdle()

        assertEquals(2, (viewModel.uiState.value as MembersUiState.Content).members.size)
    }

    @Test
    fun `the search query is passed to the repository`() = runTest(dispatcher) {
        val repository = FakeMembersRepository()
        val viewModel = MembersViewModel(repository)
        advanceUntilIdle()

        viewModel.onQueryChange("bauer")
        advanceUntilIdle()

        assertEquals("bauer", repository.lastSearch)
    }

    /**
     * Regression guard: a slow earlier search must not overwrite a faster later
     * one. The ViewModel cancels the in-flight job for exactly this reason.
     */
    @Test
    fun `a superseded search does not clobber the newer result`() = runTest(dispatcher) {
        val repository = FakeMembersRepository(members = listOf(member("stale")))
        val viewModel = MembersViewModel(repository)
        advanceUntilIdle()

        viewModel.onQueryChange("a")
        repository.members = listOf(member("fresh"))
        viewModel.onQueryChange("ab")
        advanceUntilIdle()

        val state = viewModel.uiState.value as MembersUiState.Content
        assertEquals("fresh", state.members.single().id)
        assertEquals("ab", repository.lastSearch)
    }

    @Test
    fun `a refresh picks up what was added elsewhere`() = runTest(dispatcher) {
        val repository = FakeMembersRepository(members = listOf(member("1")))
        val viewModel = MembersViewModel(repository)
        advanceUntilIdle()

        repository.members = listOf(member("1"), member("2"))
        viewModel.refresh()
        advanceUntilIdle()

        val state = viewModel.uiState.value as MembersUiState.Content
        assertEquals(2, state.members.size)
        assertTrue(!state.isRefreshing)
    }

    @Test
    fun `a failing refresh keeps the list and reports the failure`() = runTest(dispatcher) {
        val repository = FakeMembersRepository(members = listOf(member("1")))
        val viewModel = MembersViewModel(repository)
        advanceUntilIdle()

        repository.failure = ApiError.Network(IOException("offline"))
        viewModel.refresh()
        advanceUntilIdle()

        val state = viewModel.uiState.value as MembersUiState.Content
        assertEquals(1, state.members.size)
        assertTrue(state.refreshFailed)
        assertTrue(!state.isRefreshing)

        viewModel.onMessageShown()
        assertTrue(!(viewModel.uiState.value as MembersUiState.Content).refreshFailed)
    }

    /**
     * Keeping the list is right for a refresh and wrong for a search: those rows
     * do not answer what was typed, and "Aktualisieren fehlgeschlagen" would not
     * explain why they are still there.
     */
    @Test
    fun `a failing search shows the error instead of the old results`() = runTest(dispatcher) {
        val repository = FakeMembersRepository(members = listOf(member("1")))
        val viewModel = MembersViewModel(repository)
        advanceUntilIdle()

        repository.failure = ApiError.Network(IOException("offline"))
        viewModel.onQueryChange("bauer")
        advanceUntilIdle()

        assertTrue(viewModel.uiState.value is MembersUiState.Failure)
    }

    /**
     * The bug this exists for: the backend caps a page at 100, so a club bigger
     * than one page simply lost the rest, with nothing on screen to say so.
     */
    @Test
    fun `a club larger than one page keeps going`() = runTest(dispatcher) {
        val repository = FakeMembersRepository(members = (1..120).map { member("$it") })
        val viewModel = MembersViewModel(repository)
        advanceUntilIdle()
        assertEquals(50, (viewModel.uiState.value as MembersUiState.Content).members.size)

        viewModel.loadMore()
        advanceUntilIdle()
        viewModel.loadMore()
        advanceUntilIdle()

        val state = viewModel.uiState.value as MembersUiState.Content
        assertEquals(120, state.members.size)
        assertEquals(120, state.members.distinctBy { it.id }.size)
        assertEquals(listOf(1, 2, 3), repository.requestedPages)
    }

    /** The header counts the club, not the pages fetched so far. */
    @Test
    fun `the count is the club total, not what is loaded`() = runTest(dispatcher) {
        val viewModel = MembersViewModel(FakeMembersRepository((1..120).map { member("$it") }))
        advanceUntilIdle()

        val state = viewModel.uiState.value as MembersUiState.Content
        assertEquals(50, state.members.size)
        assertEquals(120, state.total)
    }

    @Test
    fun `load more past the last page asks for nothing`() = runTest(dispatcher) {
        val repository = FakeMembersRepository(members = listOf(member("1")))
        val viewModel = MembersViewModel(repository)
        advanceUntilIdle()

        repeat(5) { viewModel.loadMore() }
        advanceUntilIdle()

        assertEquals(listOf(1), repository.requestedPages)
    }

    /** Pages carry the search term, or page two would ignore what was typed. */
    @Test
    fun `paging a search stays inside the search`() = runTest(dispatcher) {
        val repository = FakeMembersRepository(members = (1..120).map { member("$it") })
        val viewModel = MembersViewModel(repository)
        advanceUntilIdle()

        viewModel.onQueryChange("bauer")
        advanceUntilIdle()
        viewModel.loadMore()
        advanceUntilIdle()

        assertEquals("bauer", repository.lastSearch)
        // A new search restarts at page one, then pages on from there.
        assertEquals(listOf(1, 1, 2), repository.requestedPages)
    }

    private fun member(id: String) = Member(
        id = id,
        memberNumber = "TV-0$id",
        firstName = "Susanne",
        lastName = "Bauer",
        email = null,
        phone = null,
        mobile = null,
        birthday = null,
        street = null,
        zipCode = null,
        city = null,
        status = MemberStatus.ACTIVE,
        category = null,
        joinedAt = "2007-04-10",
        leftAt = null,
        iban = null,
    )
}

private class FakeMembersRepository(
    var members: List<Member> = emptyList(),
    var failure: ApiError? = null,
) : MembersRepository {
    var lastSearch: String? = null

    /** Every page number asked for, in order. */
    val requestedPages = mutableListOf<Int>()

    /**
     * Pages the way the backend does, so a ViewModel that ignores meta fails.
     * The search term is recorded but not applied — what these tests check is
     * that it travels with every page, not how the backend matches it.
     */
    override suspend fun list(page: Int, perPage: Int, search: String?): ApiResult<List<Member>> {
        lastSearch = search
        requestedPages += page
        failure?.let { return ApiResult.Failure(it) }

        val totalPages = if (members.isEmpty()) 1 else (members.size + perPage - 1) / perPage
        return ApiResult.Success(
            members.drop((page - 1) * perPage).take(perPage),
            ApiMeta(total = members.size, page = page, perPage = perPage, totalPages = totalPages),
        )
    }

    override suspend fun me(): ApiResult<Member> =
        failure?.let { ApiResult.Failure(it) }
            ?: members.firstOrNull()?.let { ApiResult.Success(it) }
            ?: ApiResult.Failure(ApiError.NotFound(null))

    override suspend fun directory(
        page: Int,
        perPage: Int,
        search: String?,
    ): ApiResult<List<com.unefy.core.model.DirectoryEntry>> = failure?.let { ApiResult.Failure(it) }
        ?: ApiResult.Success(
            members.map {
                com.unefy.core.model.DirectoryEntry(it.id, it.firstName, it.lastName, it.category)
            },
        )

    override suspend fun byId(id: String): ApiResult<Member> =
        failure?.let { ApiResult.Failure(it) }
            ?: members.firstOrNull { it.id == id }
                ?.let { ApiResult.Success(it) }
            ?: ApiResult.Failure(ApiError.NotFound(null))
}
