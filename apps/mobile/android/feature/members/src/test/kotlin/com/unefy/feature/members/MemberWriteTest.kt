package com.unefy.feature.members

import com.unefy.core.model.DirectoryEntry
import com.unefy.core.model.Member
import com.unefy.core.network.ApiResult
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * What the member form puts on the wire, and what it puts on the screen before
 * the wire is available.
 *
 * The payload tests matter more than they look: these fields go straight into a
 * club's records, and the difference between an absent email and an empty one
 * is the difference between "no address" and an address of nothing — which then
 * sorts, exports and mail-merges as if it were real.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class MemberWriteTest {

    private val json = Json { ignoreUnknownKeys = true; encodeDefaults = true }

    // The form's work happens in `viewModelScope`, which is Main. Without this
    // the saves never run and every assertion reads the state before anything
    // happened.
    private val dispatcher = StandardTestDispatcher()

    @Before
    fun setUp() = Dispatchers.setMain(dispatcher)

    @After
    fun tearDown() = Dispatchers.resetMain()

    // --- Payloads ---

    @Test
    fun `blank optional fields travel as null, not as empty strings`() {
        val payload = MemberDraft(
            firstName = "Ida",
            lastName = "Beispiel",
            email = "   ",
            phone = "",
            city = "Konstanz",
        ).toCreatePayload("id-1")

        assertNull(payload.email)
        assertNull(payload.phone)
        assertEquals("Konstanz", payload.city)
    }

    @Test
    fun `names are trimmed, because a trailing space sorts a member elsewhere`() {
        val payload = MemberDraft(firstName = "  Ida ", lastName = " Beispiel  ")
            .toCreatePayload("id-1")

        assertEquals("Ida", payload.firstName)
        assertEquals("Beispiel", payload.lastName)
    }

    @Test
    fun `a cleared field is sent explicitly, so the server clears it too`() {
        // The distinction the whole payload shape exists for: PATCH only
        // touches the keys it carries, so a field the user emptied has to
        // arrive as an explicit null. Omitting it would silently keep the old
        // value and the edit would look like it never saved.
        val encoded = json.encodeToString(
            MemberDraft(firstName = "Ida", lastName = "Beispiel", email = null).toUpdatePayload(),
        )

        val keys = json.parseToJsonElement(encoded).jsonObject
        assertTrue("email" in keys)
        assertTrue(keys["email"].toString() == "null")
    }

    @Test
    fun `the creation carries the id the device chose`() {
        // Which is what makes a retry safe — see the backend's
        // test_idempotent_create.py for the other half of this contract.
        val encoded = json.encodeToString(
            MemberDraft(firstName = "Ida", lastName = "Beispiel").toCreatePayload("chosen-id"),
        )

        assertEquals(
            "chosen-id",
            json.parseToJsonElement(encoded).jsonObject["id"]?.jsonPrimitive?.content,
        )
    }

    @Test
    fun `an update carries no id, because a PATCH addresses one in the path`() {
        val encoded = json.encodeToString(
            MemberDraft(firstName = "Ida", lastName = "Beispiel").toUpdatePayload(),
        )

        assertTrue("id" !in json.parseToJsonElement(encoded).jsonObject)
    }

    // --- Validation ---

    @Test
    fun `a draft without both names is incomplete`() {
        assertTrue(MemberDraft(firstName = "Ida", lastName = "Beispiel").isComplete)
        assertTrue(!MemberDraft(firstName = "Ida", lastName = "  ").isComplete)
        assertTrue(!MemberDraft(firstName = "", lastName = "Beispiel").isComplete)
    }

    // --- The form ---

    @Test
    fun `creating saves and hands back the new id`() = runTest(dispatcher) {
        val repository = RecordingRepository()
        val viewModel = MemberFormViewModel(repository)
        viewModel.bind(null)

        viewModel.update { it.copy(firstName = "Ida", lastName = "Beispiel") }
        var saved: String? = null
        viewModel.save { saved = it }
        advanceUntilIdle()

        assertEquals("generated-id", saved)
        assertEquals(null, repository.savedId)
        assertEquals("Ida", repository.savedDraft?.firstName)
    }

    @Test
    fun `an incomplete draft is not saved`() = runTest(dispatcher) {
        val repository = RecordingRepository()
        val viewModel = MemberFormViewModel(repository)
        viewModel.bind(null)

        viewModel.update { it.copy(firstName = "Ida") }
        var saved = false
        viewModel.save { saved = true }
        advanceUntilIdle()

        assertTrue(!saved)
        assertNull(repository.savedDraft)
    }

    @Test
    fun `editing opens on the record as it stands`() = runTest(dispatcher) {
        val repository = RecordingRepository(
            existing = MemberDraft(firstName = "Ida", lastName = "Beispiel", city = "Konstanz"),
        )
        val viewModel = MemberFormViewModel(repository)

        viewModel.bind("m1")
        advanceUntilIdle()

        val state = viewModel.uiState.first()
        assertEquals("Konstanz", state.draft.city)
        assertEquals("m1", state.memberId)
        assertTrue(!state.loading)
    }

    @Test
    fun `binding twice does not discard what has been typed`() = runTest(dispatcher) {
        // The route re-binds on every recomposition that changes the key, and a
        // configuration change would otherwise wipe a half-filled form.
        val repository = RecordingRepository(existing = MemberDraft(firstName = "Ida"))
        val viewModel = MemberFormViewModel(repository)

        viewModel.bind("m1")
        advanceUntilIdle()
        viewModel.update { it.copy(firstName = "Getippt") }
        viewModel.bind("m1")
        advanceUntilIdle()

        assertEquals("Getippt", viewModel.uiState.first().draft.firstName)
    }
}

/** Records what the form asked for, and answers with whatever it was given. */
private class RecordingRepository(
    private val existing: MemberDraft? = null,
) : MembersRepository by NotUsedRepository() {

    var savedId: String? = null
    var savedDraft: MemberDraft? = null

    override suspend fun save(id: String?, draft: MemberDraft): String {
        savedId = id
        savedDraft = draft
        return id ?: "generated-id"
    }

    override fun draftFor(id: String): Flow<MemberDraft?> = flowOf(existing)
}

/**
 * Everything the form does not touch.
 *
 * Delegation rather than a dozen stub methods in [RecordingRepository]: the
 * form uses two of this interface's members, and spelling out the other nine
 * would bury which two.
 */
private class NotUsedRepository : MembersRepository {
    override fun stream(query: String): Flow<List<Member>> = flowOf(emptyList())
    override fun count(): Flow<Int> = flowOf(0)
    override fun hasSynced(): Flow<Boolean> = flowOf(true)
    override fun byIdStream(id: String): Flow<Member?> = flowOf(null)
    override suspend fun byId(id: String): ApiResult<Member> = error("not used")
    override suspend fun federations(id: String): ApiResult<List<FederationMembership>> =
        error("not used")

    override suspend fun me(): ApiResult<Member> = error("not used")
    override suspend fun directory(
        page: Int,
        perPage: Int,
        search: String?,
    ): ApiResult<List<DirectoryEntry>> = error("not used")

    override suspend fun save(id: String?, draft: MemberDraft): String = error("not used")
    override fun pendingIds(): Flow<Set<String>> = flowOf(emptySet())
    override fun draftFor(id: String): Flow<MemberDraft?> = flowOf(null)
    override suspend fun discardPending(id: String) = Unit
}
