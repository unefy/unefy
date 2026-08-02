package com.unefy.feature.attendance

import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.foundation.Canvas
import com.google.zxing.BarcodeFormat
import com.google.zxing.EncodeHintType
import com.google.zxing.qrcode.QRCodeWriter
import com.google.zxing.qrcode.decoder.ErrorCorrectionLevel

/**
 * Draws a QR code straight onto the canvas.
 *
 * No bitmap: ZXing gives a matrix of booleans, and a matrix of booleans is
 * already a drawing instruction. Going through a Bitmap would mean allocating
 * one every 30 seconds when the code rotates, and scaling it would soften edges
 * that a scanner wants crisp.
 *
 * Error correction stays at LOW deliberately. The payload is short, the code is
 * held under a scanner from 20 centimetres away, and lower correction means
 * fewer modules — which means bigger modules at the same physical size, which
 * scans faster. High correction pays off on a poster in the rain.
 */
@Composable
internal fun QrCode(
    content: String,
    modifier: Modifier = Modifier,
    foreground: Color = Color.Black,
    background: Color = Color.White,
) {
    val matrix = remember(content) {
        QRCodeWriter().encode(
            content,
            BarcodeFormat.QR_CODE,
            // Size in modules, not pixels: the writer picks the version and the
            // canvas does the scaling, so the drawing stays resolution-free.
            RENDER_SIZE,
            RENDER_SIZE,
            mapOf(
                EncodeHintType.ERROR_CORRECTION to ErrorCorrectionLevel.L,
                // Zero, because the composable's own padding is the quiet zone
                // and two sets of margin would shrink the code for nothing.
                EncodeHintType.MARGIN to 0,
            ),
        )
    }

    Canvas(modifier = modifier) { drawMatrix(matrix.width, matrix.height, matrix::get, foreground, background) }
}

private fun DrawScope.drawMatrix(
    columns: Int,
    rows: Int,
    isSet: (Int, Int) -> Boolean,
    foreground: Color,
    background: Color,
) {
    val moduleWidth = size.width / columns
    val moduleHeight = size.height / rows
    drawRect(color = background, size = size)

    for (x in 0 until columns) {
        for (y in 0 until rows) {
            if (!isSet(x, y)) continue
            drawRect(
                color = foreground,
                topLeft = Offset(x * moduleWidth, y * moduleHeight),
                // Rounded up by a hair: exact widths leave hairline gaps
                // between modules on non-integer scales, and a scanner reads
                // those gaps as noise.
                size = Size(moduleWidth + 0.5f, moduleHeight + 0.5f),
            )
        }
    }
}

/** Requested module count. ZXing rounds up to the next version that fits. */
private const val RENDER_SIZE = 256
