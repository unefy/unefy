package com.unefy.feature.attendance.nfc

import android.nfc.cardemulation.HostApduService
import android.os.Bundle
import android.os.VibrationEffect
import android.os.Vibrator
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

        CheckInApdu.outcomeOrNull(command)?.let { outcome ->
            signals.publish(outcome)
            vibrate(outcome)
            return CheckInApdu.SW_OK
        }

        if (!CheckInApdu.isSelect(command)) return CheckInApdu.SW_UNKNOWN

        // Nobody has fetched a seed on this device yet. Answered as a distinct
        // status so the reader can say "open the app once" instead of blaming
        // the code.
        val seed = seedStore.cached ?: return CheckInApdu.SW_NOT_READY

        val code = AttendanceCode.build(
            seed = seed.seed,
            memberRef = seed.memberRef,
            tenantId = seed.tenantId,
            counter = AttendanceCode.counterFor(clock.epochSeconds()),
        )
        return code.toByteArray(Charsets.US_ASCII) + CheckInApdu.SW_OK
    }

    /**
     * Called when the field is lost, including on a clean exchange.
     *
     * Nothing to undo: the code was either read or it was not, and the reader
     * decides what happened next.
     */
    override fun onDeactivated(reason: Int) = Unit

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
