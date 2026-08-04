package com.unefy.feature.attendance

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import com.unefy.core.sync.SyncCoordinator
import com.unefy.feature.attendance.nfc.CardEvent
import com.unefy.feature.attendance.nfc.CheckInApdu
import com.unefy.feature.attendance.nfc.NfcCheckInSignals
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull

/**
 * Entity name of the addressed hint this screen listens for.
 *
 * The contract with `CHECK_IN_SIGNAL` in backend/app/services/attendance.py. Not a
 * sync collection and deliberately not one: there is no `/sync/check-ins` to drain,
 * because a member may know about their own attendance and not about anyone else's.
 * The frame is addressed to one account on the server side; this app never has to
 * check that it was meant for it.
 */
internal const val CHECK_IN_SIGNAL = "check-ins"

sealed interface MemberCodeUiState {
    data object Loading : MemberCodeUiState

    data class Content(
        val code: String,
        /** Counts down to the next rotation, so the code is visibly alive. */
        val secondsRemaining: Long,
        /**
         * True when the code is computed from a seed the server would now
         * consider expired. It very likely still verifies — the backend allows
         * two periods of grace — but the member should know why it might not.
         */
        val seedStale: Boolean,
    ) : MemberCodeUiState

    /**
     * Somebody scanned this code and it went through.
     *
     * The whole point of showing it: until now the member held out a QR and
     * learned nothing, because the check-in happens on the supervisor's device.
     */
    /** Read by a scanner; the outcome has not come back yet. */
    data object Read : MemberCodeUiState

    data class Confirmed(val sessionTitle: String?) : MemberCodeUiState

    data class Failure(val error: ApiError) : MemberCodeUiState

    /** The account has no member record, so there is nobody to check in. */
    data object NoMembership : MemberCodeUiState
}

/**
 * Shows the member's rotating check-in code.
 *
 * The loop is the feature: a new code every 30 seconds, computed locally. The
 * network is only ever consulted for the seed, and only when the stored one has
 * run out — so the screen keeps working in a range with no signal, which is
 * where it is actually used.
 */
@HiltViewModel
class MemberCodeViewModel @Inject constructor(
    private val repository: AttendanceRepository,
    private val seedStore: SeedStore,
    private val clock: AttendanceClock,
    private val nfcSignals: NfcCheckInSignals,
    private val coordinator: SyncCoordinator,
) : ViewModel() {

    private val _uiState = MutableStateFlow<MemberCodeUiState>(MemberCodeUiState.Loading)
    val uiState: StateFlow<MemberCodeUiState> = _uiState.asStateFlow()

    /**
     * A tap said yes. Kept apart from [seenOnServer] because a QUEUED outcome
     * is a confirmation the server has never heard of — the scanner was
     * offline — and the poll must not read its absence as a retraction.
     */
    private var tapConfirmed = false

    /**
     * The poll has seen this check-in on the server at least once. Only then
     * does its disappearance mean somebody took it back, rather than that the
     * scanner's queue has not drained yet.
     */
    private var seenOnServer = false

    /** When the code last left over NFC, so [start]'s loop can hold Read briefly. */
    private var readAtEpochSeconds = 0L

    /**
     * Cuts the current tick short, so the loop polls now instead of on schedule.
     *
     * Conflated: it says "there is news", and two of those mean what one means.
     *
     * A channel rather than a second coroutine that polls by itself. The state here
     * — has a tap confirmed, has the server ever admitted the record, is the screen
     * holding [MemberCodeUiState.Read] — is a small state machine, and two
     * coroutines writing it would interleave on the two suspension points inside a
     * poll. Waking the one owner keeps it a state machine.
     */
    private val wake = Channel<Unit>(Channel.CONFLATED)

    init {
        start()

        // The server-side half of the same idea as the tap: the check-in happens on
        // the supervisor's phone, so this one is told about it. Only the news, not
        // the record — the poll below re-reads the endpoint that is scoped to this
        // account, so nothing is ever believed on the strength of a stream frame.
        //
        // Not a replacement for the poll. The stream needs a connection, and the
        // range in the basement is exactly where it will not be there; the poll is
        // what still works, and this is what makes the good case instant.
        viewModelScope.launch {
            coordinator.signals(CHECK_IN_SIGNAL).collect { wake.trySend(Unit) }
        }

        // The instant path. A tap tells this phone directly, in the same
        // second and without a server — which is the only way the confirmation
        // works in a basement, where the poll below cannot reach anything.
        viewModelScope.launch {
            nfcSignals.events.collect { event ->
                when (event) {
                    // Not a confirmation, but not nothing either: the code left
                    // this phone and the answer is a moment away.
                    CardEvent.Read -> {
                        readAtEpochSeconds = clock.epochSeconds()
                        _uiState.value = MemberCodeUiState.Read
                    }

                    is CardEvent.Result -> when (event.outcome) {
                        CheckInApdu.Outcome.RECORDED, CheckInApdu.Outcome.QUEUED,
                        CheckInApdu.Outcome.ALREADY_PRESENT,
                        -> {
                            tapConfirmed = true
                            _uiState.value = MemberCodeUiState.Confirmed(sessionTitle = null)
                        }

                        // Back to the code: a refusal means the supervisor will
                        // ask for another go, and there is nothing to hold out
                        // if the screen has moved on.
                        CheckInApdu.Outcome.REJECTED -> {
                            tapConfirmed = false
                            _uiState.value = MemberCodeUiState.Loading
                        }
                    }
                }
            }
        }
    }

    fun retry() = start()

    private fun start() {
        tapConfirmed = false
        seenOnServer = false
        readAtEpochSeconds = 0L
        _uiState.value = MemberCodeUiState.Loading
        viewModelScope.launch {
            val seed = obtainSeed() ?: return@launch
            // Anything already recorded before this screen opened is history,
            // not the confirmation of what is about to happen.
            val openedAt = clock.epochSeconds()
            var tick = 0
            var woken = false

            // Ticks once a second rather than once per window: the countdown is
            // what tells a member the code is live rather than a frozen image,
            // and a stuck screen is indistinguishable from a working one
            // without it. The loop never ends on its own — even a confirmed
            // check-in can be taken back at the scanner or in the web app, and
            // this loop is the only place the phone would hear about it.
            while (isActive) {
                val now = clock.epochSeconds()

                // The fallback under both instant paths, and still the only one
                // that needs nothing but a request: a tap answers through
                // nfcSignals, a camera scan through the change stream, and this
                // catches the case where neither arrived — a stream that is down,
                // a frame lost in a reconnect gap, a phone pulled away mid-tap.
                // Offline it simply fails and the code stays up.
                val cadence = if (tapConfirmed || seenOnServer) {
                    CONFIRMED_POLL_EVERY_TICKS
                } else {
                    POLL_EVERY_TICKS
                }
                val due = tick++ % cadence == 0
                if (due || woken) {
                    val result = repository.latestOwnCheckIn()
                    // Only a definite answer moves anything. A failed poll is a
                    // dead network, not a missing check-in.
                    if (result is ApiResult.Success) {
                        val own = result.data
                        if (own != null && own.checkedInAtEpochSeconds >= openedAt) {
                            seenOnServer = true
                            _uiState.value = MemberCodeUiState.Confirmed(own.sessionTitle)
                        } else if (seenOnServer) {
                            // It was on the server and now it is not: the
                            // supervisor took it back. Back to the code, so the
                            // member is not left trusting a green screen the
                            // server no longer stands behind.
                            seenOnServer = false
                            tapConfirmed = false
                        }
                    }
                }

                // The loop owns the screen only while nothing eventful is on
                // it: a confirmation stays up (a QUEUED tap may never appear on
                // the server), and a just-read code gets a moment for its
                // outcome before the rotation takes over again.
                val confirmed = tapConfirmed || seenOnServer
                val awaitingTapResult = _uiState.value is MemberCodeUiState.Read &&
                    now - readAtEpochSeconds < READ_PATIENCE_SECONDS
                if (!confirmed && !awaitingTapResult) {
                    _uiState.value = MemberCodeUiState.Content(
                        code = AttendanceCode.build(
                            seed = seed.seed,
                            memberRef = seed.memberRef,
                            tenantId = seed.tenantId,
                            counter = AttendanceCode.counterFor(now),
                        ),
                        secondsRemaining = AttendanceCode.secondsUntilNextCode(now),
                        seedStale = now >= seed.expiresAtEpochSeconds,
                    )
                }
                // A tick, unless the doorbell rings first. That is the whole
                // difference between "within two seconds" and "now".
                woken = withTimeoutOrNull(TICK_MILLIS) { wake.receive() } != null
            }
        }
    }

    /**
     * The stored seed if it is still current, a fresh one otherwise, and the
     * stored one anyway if the network says no.
     *
     * That last fallback is the offline case: an expired seed still verifies
     * for two more periods on the server, so showing a probably-good code beats
     * showing an error to someone standing at the door.
     */
    private suspend fun obtainSeed(): AttendanceSeed? {
        val stored = seedStore.read()
        if (stored != null && clock.epochSeconds() < stored.expiresAtEpochSeconds) {
            return stored
        }

        return when (val result = repository.seed()) {
            is ApiResult.Success -> result.data.also { seedStore.write(it) }
            is ApiResult.Failure -> stored ?: run {
                _uiState.value = failureFor(result.error)
                null
            }
        }
    }

    private fun failureFor(error: ApiError): MemberCodeUiState =
        // A 404 here means one specific thing: the signed-in account is not
        // linked to a member. Saying so beats a generic error, because the
        // remedy is to ask the board rather than to retry.
        if (error is ApiError.NotFound) {
            MemberCodeUiState.NoMembership
        } else {
            MemberCodeUiState.Failure(error)
        }

    private companion object {
        const val TICK_MILLIS = 1_000L

        /**
         * Every two seconds while the code is on screen.
         *
         * This is the fallback for a QR scan, or for a tap whose reply never
         * landed because the phone was pulled away. Five seconds was long
         * enough to read as "nothing happened"; the screen is only up for a
         * moment, so the extra requests cost little.
         */
        const val POLL_EVERY_TICKS = 2

        /**
         * Every ten seconds once confirmed. The only thing left to learn is a
         * retraction, which is rare and not urgent — but a screen that can
         * never unlearn its green tick would lie for as long as it stays open.
         */
        const val CONFIRMED_POLL_EVERY_TICKS = 10

        /**
         * How long "Gelesen" may hold the screen while the tap's outcome is on
         * its way. Past that the phones have separated without an answer and
         * the rotating code is the only useful thing to show.
         */
        const val READ_PATIENCE_SECONDS = 5L
    }
}

/** Injected so the code loop can be driven from a test without waiting. */
fun interface AttendanceClock {
    fun epochSeconds(): Long
}
