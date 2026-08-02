package com.unefy.feature.members

import com.unefy.core.model.Member
import com.unefy.core.model.MemberStatus
import com.unefy.core.network.ApiError
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

    override suspend fun list(page: Int, perPage: Int, search: String?): ApiResult<List<Member>> {
        lastSearch = search
        return failure?.let { ApiResult.Failure(it) } ?: ApiResult.Success(members)
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
