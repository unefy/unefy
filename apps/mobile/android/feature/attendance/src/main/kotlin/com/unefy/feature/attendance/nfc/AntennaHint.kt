package com.unefy.feature.attendance.nfc

import android.nfc.NfcAdapter
import android.os.Build
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.height
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.unefy.core.designsystem.theme.UnefySpacing

/** Where this phone's NFC antenna sits, in millimetres from the bottom-left. */
internal data class AntennaSpot(val deviceWidthMm: Int, val deviceHeightMm: Int, val xMm: Int, val yMm: Int)

/**
 * Reads the antenna position from the platform.
 *
 * Available from Android 14. Below that, and on devices that decline to say,
 * this returns null and the caller falls back to prose — there is no way to
 * guess, and guessing wrongly is worse than admitting it.
 */
internal fun antennaSpot(adapter: NfcAdapter?): AntennaSpot? {
    if (adapter == null || Build.VERSION.SDK_INT < Build.VERSION_CODES.UPSIDE_DOWN_CAKE) return null
    val info = adapter.nfcAntennaInfo ?: return null
    val antenna = info.availableNfcAntennas.firstOrNull() ?: return null
    return AntennaSpot(
        deviceWidthMm = info.deviceWidth,
        deviceHeightMm = info.deviceHeight,
        xMm = antenna.locationX,
        yMm = antenna.locationY,
    )
}

/**
 * A phone outline with the antenna marked, drawn to scale.
 *
 * Hunting for the coupling point was the single most frustrating part of
 * tapping — two small antennas at unknown positions, and the only feedback was
 * success or nothing. The platform knows exactly where this phone's antenna is,
 * so there is no reason to make anybody guess. It cannot help with the *other*
 * phone, which is why both screens show their own.
 */
@Composable
internal fun AntennaHint(caption: String, modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val spot = remember { antennaSpot(NfcAdapter.getDefaultAdapter(context)) }

    val outline = MaterialTheme.colorScheme.onSurfaceVariant
    val marker = MaterialTheme.colorScheme.primary

    Column(
        modifier = modifier,
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(UnefySpacing.xs),
    ) {
        if (spot == null) {
            // No prose fallback here: the caller already shows the general
            // hint, and a second vague sentence would only add noise.
            return@Column
        }

        Canvas(
            modifier = Modifier
                .height(DIAGRAM_HEIGHT)
                .aspectRatio(spot.deviceWidthMm.toFloat() / spot.deviceHeightMm),
        ) {
            drawRoundRect(
                color = outline,
                cornerRadius = androidx.compose.ui.geometry.CornerRadius(size.minDimension / 8),
                style = Stroke(width = 3f),
            )
            // The platform measures from the bottom-left; the canvas from the
            // top-left, so the vertical axis flips.
            val x = size.width * spot.xMm / spot.deviceWidthMm
            val y = size.height * (1f - spot.yMm.toFloat() / spot.deviceHeightMm)
            drawCircle(color = marker, radius = size.minDimension / 9, center = Offset(x, y))
        }

        Text(
            text = caption,
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

private val DIAGRAM_HEIGHT = 96.dp
