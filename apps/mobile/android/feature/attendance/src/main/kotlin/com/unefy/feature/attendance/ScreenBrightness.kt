package com.unefy.feature.attendance

import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
import android.view.WindowManager
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.ui.platform.LocalContext

/**
 * Turns the screen to full brightness and keeps it awake while a composable is
 * on screen, restoring both when it leaves.
 *
 * Not a flourish. A QR is read by a camera pointed at an emissive panel, and a
 * phone dimmed by auto-brightness in a badly lit hall is the single most common
 * reason a code will not scan — the same reason boarding passes and payment apps
 * all do this. Keeping the screen awake matters for the other half: the member
 * holds the phone out and waits, touching nothing, and a screen that dims to
 * black mid-queue has to be woken and navigated back to.
 *
 * Window-scoped, so it affects this app while this screen is visible and nothing
 * else — the system brightness setting is never touched.
 */
@Composable
internal fun KeepScreenBrightAndAwake() {
    val activity = LocalContext.current.findActivity() ?: return

    DisposableEffect(activity) {
        val window = activity.window
        val previous = window.attributes.screenBrightness

        window.attributes = window.attributes.apply {
            screenBrightness = WindowManager.LayoutParams.BRIGHTNESS_OVERRIDE_FULL
        }
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        onDispose {
            // Back to whatever it was, which is normally
            // BRIGHTNESS_OVERRIDE_NONE — "let the system decide again".
            window.attributes = window.attributes.apply { screenBrightness = previous }
            window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }
    }
}

/**
 * Keeps the screen on without touching brightness.
 *
 * For the scanner. NFC reader mode only runs while this screen is showing, so a
 * phone that locks after a minute stops being able to read anything — and from
 * the outside that is indistinguishable from NFC being broken, which is exactly
 * how it presented. A supervisor puts the phone down between people; it has to
 * still be listening when the next one arrives.
 *
 * Brightness is left alone here: nobody is reading this screen from a metre
 * away, and an evening at full brightness costs a battery the QR screen's few
 * seconds do not.
 */
@Composable
internal fun KeepScreenAwake() {
    val activity = LocalContext.current.findActivity() ?: return

    DisposableEffect(activity) {
        activity.window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        onDispose { activity.window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON) }
    }
}

private tailrec fun Context.findActivity(): Activity? = when (this) {
    is Activity -> this
    is ContextWrapper -> baseContext.findActivity()
    // A preview or a test host has no window to brighten, and that is fine.
    else -> null
}
