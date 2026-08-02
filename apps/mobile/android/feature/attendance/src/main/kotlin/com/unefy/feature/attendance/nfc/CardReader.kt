package com.unefy.feature.attendance.nfc

import android.app.Activity
import android.nfc.NfcAdapter
import android.nfc.tech.IsoDep
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.ui.platform.LocalContext
import java.io.IOException

/** What a tap produced, before the check-in is attempted. */
sealed interface TapResult {
    /** The member's code, ready to go through the same path as a scanned one. */
    data class Code(val value: String, val respond: (CheckInApdu.Outcome) -> Unit) : TapResult

    /** A unefy phone that has never fetched a seed. */
    data object NotReady : TapResult

    /** Something was held to the phone, but it was not one of ours. */
    data object Foreign : TapResult
}

/**
 * Reads a member's phone while this screen is up.
 *
 * Reader mode rather than the foreground dispatch: dispatch delivers tags
 * through intents and would restart the activity mid-scan, taking the camera
 * and the chosen session with it. Reader mode keeps the exchange inside this
 * screen, where the session is already known.
 *
 * NDEF checking is skipped because there is no NDEF here — this is a raw
 * ISO-DEP conversation with an app on the other phone, and letting Android look
 * for a tag format first only adds latency to something a person is holding
 * still with their arm out.
 */
@Composable
internal fun NfcReader(enabled: Boolean, onTap: (TapResult) -> Unit) {
    val context = LocalContext.current
    val activity = context as? Activity ?: return
    val currentOnTap by rememberUpdatedState(onTap)

    DisposableEffect(activity, enabled) {
        val adapter = NfcAdapter.getDefaultAdapter(activity)
        if (adapter == null || !enabled) return@DisposableEffect onDispose { }

        adapter.enableReaderMode(
            activity,
            { tag -> currentOnTap(exchange(IsoDep.get(tag))) },
            NfcAdapter.FLAG_READER_NFC_A or
                NfcAdapter.FLAG_READER_NFC_B or
                NfcAdapter.FLAG_READER_SKIP_NDEF_CHECK,
            null,
        )
        onDispose { adapter.disableReaderMode(activity) }
    }
}

/**
 * One tap, start to finish.
 *
 * The connection is held open across the check-in so the outcome can be handed
 * back on the same link — reconnecting would mean asking the person to tap
 * twice, once to be read and once to be told.
 */
private fun exchange(isoDep: IsoDep?): TapResult {
    if (isoDep == null) return TapResult.Foreign

    return try {
        isoDep.connect()
        // Generous: the card side may have to wake a process before it answers.
        isoDep.timeout = TIMEOUT_MILLIS

        val response = isoDep.transceive(CheckInApdu.SELECT)
        when {
            response.endsWith(CheckInApdu.SW_NOT_READY) -> TapResult.NotReady

            response.size > STATUS_WORD_LENGTH && response.endsWith(CheckInApdu.SW_OK) -> {
                val code = String(
                    response.copyOfRange(0, response.size - STATUS_WORD_LENGTH),
                    Charsets.US_ASCII,
                )
                TapResult.Code(code) { outcome ->
                    // Best effort: the phone may already have been pulled away,
                    // and a check-in that happened must not be undone because
                    // the courtesy reply did not land.
                    runCatching {
                        isoDep.transceive(CheckInApdu.resultCommand(outcome))
                        isoDep.close()
                    }
                }
            }

            else -> TapResult.Foreign
        }
    } catch (_: IOException) {
        // A tap that moved. The person will try again, and saying "hold still"
        // is the reader UI's job, not an exception's.
        TapResult.Foreign
    }
}

private fun ByteArray.endsWith(suffix: ByteArray): Boolean =
    size >= suffix.size && copyOfRange(size - suffix.size, size).contentEquals(suffix)

private const val STATUS_WORD_LENGTH = 2
private const val TIMEOUT_MILLIS = 2_000
