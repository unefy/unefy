package com.unefy.feature.attendance.nfc

import android.nfc.cardemulation.HostApduService
import android.os.Bundle
import android.os.VibrationEffect
import android.os.Vibrator
import android.util.Log
import androidx.core.content.getSystemService
import com.unefy.feature.attendance.AttendanceClock
import com.unefy.feature.attendance.AttendanceCode
import com.unefy.feature.attendance.SeedStore
import dagger.hilt.android.AndroidEntryPoint
import javax.inject.Inject
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeoutOrNull

/**
 * The member's phone, acting as a contactless card.
 *
 * This is the half of NFC that makes it worth having over the QR: the phone is
 * *told* it was read, in the same moment, without a server. The camera path
 * cannot do that — the check-in happens on somebody else's device, so the
 * member's phone has to ask a server that a basement may not reach.
 *
 * Android routes by AID, so this works with the app closed and the screen
 * merely unlocked. That is also why the vibration happens here rather than in a
 * screen: there may be no screen.
 *
 * `processCommandApdu` runs on the main thread and the reader will not wait, so
 * everything it touches has to be in memory already — hence [SeedStore.cached]
 * and the preload below.
 */
@AndroidEntryPoint
class MemberCardService : HostApduService() {

    @Inject
    lateinit var seedStore: SeedStore

    @Inject
    lateinit var clock: AttendanceClock

    @Inject
    lateinit var signals: NfcCheckInSignals

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onCreate() {
        super.onCreate()
        // Warms the cache. The service is created when the AID is first routed
        // to it, which is typically well before the phone is held to a reader.
        scope.launch { seedStore.read() }
    }

    override fun onDestroy() {
        scope.cancel()
        super.onDestroy()
    }

    override fun processCommandApdu(commandApdu: ByteArray?, extras: Bundle?): ByteArray {
        val command = commandApdu ?: return CheckInApdu.SW_UNKNOWN
        Log.i(TAG, "apdu in: ${command.size} bytes")

        CheckInApdu.outcomeOrNull(command)?.let { outcome ->
            signals.publish(outcome)
            vibrate(outcome)
            return CheckInApdu.SW_OK
        }

        if (!CheckInApdu.isSelect(command)) return CheckInApdu.SW_UNKNOWN

        // Felt the moment contact is made, before anything is decided. The
        // member is holding two phones together hunting for the spot, and the
        // result buzz may be a second away or never come if the tap slips.
        tick()

        // Warm cache normally. Cold only when the tap itself started this
        // process, and then a short blocking read beats failing the tap — the
        // alternative is telling somebody with their phone against a reader to
        // open an app and try again. Bounded well inside the ISO-DEP timeout,
        // and skipped entirely on every subsequent tap.
        val seed = seedStore.cached ?: runBlocking {
            withTimeoutOrNull(COLD_READ_MILLIS) { seedStore.read() }
        }

        // Genuinely nothing stored: this account has never opened the check-in
        // screen. A distinct status, so the reader says "open the app once"
        // rather than blaming the code.
        if (seed == null) {
            Log.i(TAG, "no seed stored; answering not-ready")
            return CheckInApdu.SW_NOT_READY
        }

        val code = AttendanceCode.build(
            seed = seed.seed,
            memberRef = seed.memberRef,
            tenantId = seed.tenantId,
            counter = AttendanceCode.counterFor(clock.epochSeconds()),
        )
        return code.toByteArray(Charsets.US_ASCII) + CheckInApdu.SW_OK
    }

    private companion object {
        /** Short enough that a reader waiting on us does not give up first. */
        const val COLD_READ_MILLIS = 400L
        const val TAG = "unefy.nfc.card"
    }

    /**
     * Called when the field is lost, including on a clean exchange.
     *
     * Nothing to undo: the code was either read or it was not, and the reader
     * decides what happened next.
     */
    override fun onDeactivated(reason: Int) = Unit

    /** A single light tick: "we touched", not "you are checked in". */
    private fun tick() {
        getSystemService<Vibrator>()
            ?.vibrate(VibrationEffect.createOneShot(25, VibrationEffect.DEFAULT_AMPLITUDE))
    }

    private fun vibrate(outcome: CheckInApdu.Outcome) {
        val vibrator = getSystemService<Vibrator>() ?: return
        // Two short taps for success, one long buzz otherwise — distinguishable
        // in a pocket, which is where this phone often is.
        val effect = if (outcome == CheckInApdu.Outcome.RECORDED ||
            outcome == CheckInApdu.Outcome.QUEUED
        ) {
            VibrationEffect.createWaveform(longArrayOf(0, 40, 80, 40), -1)
        } else {
            VibrationEffect.createOneShot(300, VibrationEffect.DEFAULT_AMPLITUDE)
        }
        vibrator.vibrate(effect)
    }
}
