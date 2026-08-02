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

    private val _outcomes = MutableSharedFlow<CheckInApdu.Outcome>(extraBufferCapacity = 4)
    val outcomes: SharedFlow<CheckInApdu.Outcome> = _outcomes.asSharedFlow()

    fun publish(outcome: CheckInApdu.Outcome) {
        _outcomes.tryEmit(outcome)
    }
}
