package com.unefy.feature.attendance

import androidx.annotation.OptIn
import androidx.camera.core.ExperimentalGetImage
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage

/**
 * Reads unefy check-in codes out of the camera stream.
 *
 * Restricted to QR: telling ML Kit which format to expect skips the detectors
 * for every other symbology, which is most of the per-frame cost. Codes that
 * are not ours are dropped here rather than sent to the server, so pointing the
 * camera at a parcel label does not produce an error toast.
 */
internal class QrAnalyzer(private val onCode: (String) -> Unit) : ImageAnalysis.Analyzer {

    private val scanner = BarcodeScanning.getClient(
        com.google.mlkit.vision.barcode.BarcodeScannerOptions.Builder()
            .setBarcodeFormats(Barcode.FORMAT_QR_CODE)
            .build(),
    )

    @OptIn(ExperimentalGetImage::class)
    override fun analyze(image: ImageProxy) {
        val frame = image.image
        if (frame == null) {
            image.close()
            return
        }

        scanner.process(InputImage.fromMediaImage(frame, image.imageInfo.rotationDegrees))
            .addOnSuccessListener { barcodes ->
                barcodes.asSequence()
                    .mapNotNull { it.rawValue }
                    .filter { it.startsWith(CODE_PREFIX, ignoreCase = true) }
                    .firstOrNull()
                    ?.let(onCode)
            }
            // Closing in a completion listener, not after `process`: the frame
            // has to stay alive until ML Kit is done with it, and closing early
            // starves the analyzer of every subsequent frame.
            .addOnCompleteListener { image.close() }
    }

    private companion object {
        val CODE_PREFIX = "${AttendanceCode.VERSION}."
    }
}
