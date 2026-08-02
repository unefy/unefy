package com.unefy.feature.attendance

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

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
) : ViewModel() {

    private val _uiState = MutableStateFlow<MemberCodeUiState>(MemberCodeUiState.Loading)
    val uiState: StateFlow<MemberCodeUiState> = _uiState.asStateFlow()

    init {
        start()
    }

    fun retry() = start()

    private fun start() {
        _uiState.value = MemberCodeUiState.Loading
        viewModelScope.launch {
            val seed = obtainSeed() ?: return@launch
            // Anything already recorded before this screen opened is history,
            // not the confirmation of what is about to happen.
            val openedAt = clock.epochSeconds()
            var tick = 0

            // Ticks once a second rather than once per window: the countdown is
            // what tells a member the code is live rather than a frozen image,
            // and a stuck screen is indistinguishable from a working one
            // without it.
            while (isActive) {
                val now = clock.epochSeconds()

                // Polled rather than pushed. FCM is not built, and a request
                // every few seconds for the minute this screen is open is a far
                // smaller cost than a member who cannot tell whether they are
                // checked in. Offline it simply fails and the code stays up.
                if (tick++ % POLL_EVERY_TICKS == 0) {
                    val own = (repository.latestOwnCheckIn() as? ApiResult.Success)?.data
                    if (own != null && own.checkedInAtEpochSeconds >= openedAt) {
                        _uiState.value = MemberCodeUiState.Confirmed(own.sessionTitle)
                        return@launch
                    }
                }

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
                delay(TICK_MILLIS)
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

        /** Every five seconds. Fast enough to feel immediate at the door. */
        const val POLL_EVERY_TICKS = 5
    }
}

/** Injected so the code loop can be driven from a test without waiting. */
fun interface AttendanceClock {
    fun epochSeconds(): Long
}
