package com.unefy.feature.attendance.nfc

import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow

/**
 * Carries an NFC check-in result from the card service to whatever screen is up.
 *
 * A shared flow rather than state: this is an event that happened once, and a
 * screen opened afterwards should not be greeted by a stale confirmation from
 * ten minutes ago. `extraBufferCapacity` so the service, which is not in a
 * coroutine, can emit without suspending.
 *
 * The card service works whether or not the app is on screen — Android routes
 * by AID — so the tap has to be felt even with nothing collecting here. That is
 * why the service vibrates itself rather than leaving it to the UI.
 */
@Singleton
class NfcCheckInSignals @Inject constructor() {

    private val _events = MutableSharedFlow<CardEvent>(extraBufferCapacity = 4)
    val events: SharedFlow<CardEvent> = _events.asSharedFlow()

    fun publish(event: CardEvent) {
        _events.tryEmit(event)
    }
}

/** What happened to this phone's card, in the order it happens. */
sealed interface CardEvent {
    /**
     * The code was read. Nothing decided yet.
     *
     * Worth its own event: the reader can only report the outcome while the
     * phones are still touching, and people pull away as soon as they feel the
     * first buzz. Saying "read — hold on a second" is what makes the wait
     * legible instead of looking like nothing happened.
     */
    data object Read : CardEvent

    data class Result(val outcome: CheckInApdu.Outcome) : CardEvent
}
