package com.unefy.feature.attendance.nfc

import android.app.Activity
import android.nfc.NfcAdapter
import android.content.Context
import android.content.ContextWrapper
import android.nfc.tech.IsoDep
import android.util.Log
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import java.io.IOException

/**
 * Whether this screen can read a phone at all.
 *
 * Shown to the supervisor rather than kept in a log. "Nothing happens when I
 * tap" has several causes that look identical from the outside — NFC switched
 * off, no session chosen, no chip in the phone — and guessing between them
 * from the outside is what made this frustrating.
 */
enum class NfcState {
    /** Reader is live; hold a phone against it. */
    Listening,

    /** The phone has NFC, but it is switched off in system settings. */
    SwitchedOff,

    /** Nothing to check into yet. */
    Idle,

    /** No NFC hardware. The QR path is the only one here. */
    Unavailable,
}

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
internal fun NfcReader(
    enabled: Boolean,
    onDetected: () -> Unit,
    onState: (NfcState) -> Unit = {},
    onTap: (TapResult) -> Unit,
) {
    val context = LocalContext.current
    // Unwrapped rather than cast: LocalContext is not always the Activity
    // itself, and a plain cast silently returned null — which disabled reader
    // mode entirely while looking exactly like NFC not working.
    val activity = context.findActivity()
    if (activity == null) {
        onState(NfcState.Unavailable)
        return
    }
    val currentOnTap by rememberUpdatedState(onTap)
    val currentOnDetected by rememberUpdatedState(onDetected)

    val lifecycleOwner = LocalLifecycleOwner.current

    DisposableEffect(activity, lifecycleOwner, enabled) {
        val adapter = NfcAdapter.getDefaultAdapter(activity)
        when {
            adapter == null -> onState(NfcState.Unavailable)
            !adapter.isEnabled -> onState(NfcState.SwitchedOff)
            !enabled -> onState(NfcState.Idle)
            else -> onState(NfcState.Listening)
        }
        if (adapter == null || !adapter.isEnabled || !enabled) {
            Log.i(TAG, "reader off (adapter=${adapter != null}, on=${adapter?.isEnabled}, enabled=$enabled)")
            return@DisposableEffect onDispose { }
        }

        // Tied to the lifecycle, not to composition. Android disables reader
        // mode whenever the activity pauses — a notification shade, an app
        // switch, the screen blanking — and a composition-scoped setup never
        // learns of it, because a pause does not dispose anything. The result
        // was NFC that worked for about a minute and then silently never
        // again until the screen was left and re-entered, which is impossible
        // to tell apart from "NFC is broken".
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_RESUME -> {
                    Log.i(TAG, "reader mode on")
                    adapter.enableReaderMode(
                        activity,
                        { tag ->
                            Log.i(TAG, "tag discovered: ${tag.techList.joinToString()}")
                            // Announced before the exchange, not after. Finding
                            // the spot where two phones' antennas meet is
                            // guesswork, and until this the first sign of
                            // contact was the finished check-in — a second or
                            // more later, by which time the hand has moved on.
                            currentOnDetected()
                            currentOnTap(exchange(IsoDep.get(tag)))
                        },
                        NfcAdapter.FLAG_READER_NFC_A or
                            NfcAdapter.FLAG_READER_NFC_B or
                            NfcAdapter.FLAG_READER_SKIP_NDEF_CHECK,
                        null,
                    )
                }

                Lifecycle.Event.ON_PAUSE -> {
                    Log.i(TAG, "reader mode off (paused)")
                    adapter.disableReaderMode(activity)
                }

                else -> Unit
            }
        }

        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            Log.i(TAG, "reader mode off (left screen)")
            lifecycleOwner.lifecycle.removeObserver(observer)
            adapter.disableReaderMode(activity)
        }
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
        Log.i(TAG, "select answered with ${response.size} bytes")
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
    } catch (e: IOException) {
        Log.i(TAG, "tap lost: ${e.message}")
        // A tap that moved. The person will try again, and saying "hold still"
        // is the reader UI's job, not an exception's.
        TapResult.Foreign
    }
}

private fun ByteArray.endsWith(suffix: ByteArray): Boolean =
    size >= suffix.size && copyOfRange(size - suffix.size, size).contentEquals(suffix)

private tailrec fun Context.findActivity(): Activity? = when (this) {
    is Activity -> this
    is ContextWrapper -> baseContext.findActivity()
    else -> null
}

private const val TAG = "unefy.nfc.reader"
private const val STATUS_WORD_LENGTH = 2
private const val TIMEOUT_MILLIS = 2_000
