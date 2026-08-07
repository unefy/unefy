package com.unefy.feature.scoring

import android.graphics.Bitmap
import android.graphics.Color
import androidx.core.graphics.createBitmap
import com.unefy.core.model.scoring.DetectedHit
import com.unefy.core.model.scoring.HitDetector
import com.unefy.core.model.scoring.TargetFit
import com.unefy.core.model.scoring.TargetGeometry
import com.unefy.core.model.scoring.TargetLocator
import kotlin.math.max
import kotlin.math.roundToInt

/**
 * A photographed target, located and squared up.
 *
 * The Android-facing half of [TargetLocator]: that one is pure Kotlin working on
 * an `IntArray` so it can be unit-tested and cross-checked against the Python
 * reference; this one deals with `Bitmap` and the camera.
 */
data class TargetPhoto(
    /** The photo, rectified and cropped square around the target. */
    val rectified: Bitmap,
    /** Where the aiming mark sat in the ORIGINAL photo, for the overlay. */
    val fit: TargetFit,
    /** Size of the photo the fit refers to. */
    val sourceWidth: Int,
    val sourceHeight: Int,
    /**
     * The holes found in [rectified], normalised to the scoring radius.
     *
     * A proposal and nothing more: they are placed for the shooter to correct,
     * because no photograph can say which holes belong to the series being
     * recorded (ml/NOTES-real-targets.md §1).
     */
    val hits: List<DetectedHit> = emptyList(),
) {
    /** True when the photo is too oblique to trust — the app warns rather than refuses. */
    val oblique: Boolean get() = fit.oblique
}

object TargetPhotoAnalyzer {

    /**
     * Side of the rectified square.
     *
     * Raised from 640 for what comes next. At 640 the whole 625 mm frame is
     * 1 mm per pixel, so a 9 mm bullet hole is nine pixels across and a 4.5 mm
     * pellet four — too little for any detector, and too little for a person
     * placing a shot precisely.
     *
     * 1600 rather than something larger: it is 2.56 pixels per millimetre, and
     * that number was chosen by scoring [HitDetector] at each size against the
     * hand-checked holes. Coarser loses holes; finer loses precision, because
     * paper grain and JPEG noise start resolving into blobs the size of a small
     * hole. Both directions were measured (ml/scripts/score_hits.py).
     */
    // 1472 over a 1.15 frame is 2.56 px/mm, the resolution the hit detector was
    // scored at. It follows CROP_MARGIN: leaving it at 1600 would have made the
    // crop finer at 2.78, where paper grain starts resolving into hole-sized
    // blobs (ml/scripts/rectify.py CROP_SIZE).
    private const val CROP_SIZE = 1472

    /**
     * How much beyond ring 1 the crop reaches.
     *
     * Must match what the canvas draws, or the photo underneath the rings is
     * scaled differently from them — which it was, 1.15 against 1.09.
     */
    private const val CROP_MARGIN = TargetGeometry.FRAME_TO_SCORING

    /**
     * Locate the target in [photo] and produce a squared-up crop.
     *
     * Returns null when no plausible target is found — a photo of the floor, or
     * of a target too far away to measure. The caller keeps manual entry.
     */
    fun analyze(photo: Bitmap, geometry: TargetGeometry): TargetPhoto? {
        // Analysis runs on a downscaled copy: a 12 MP frame costs seconds and
        // finds nothing a 1024px one does not. The fit is scaled back afterwards
        // so the overlay lands on the full-resolution photo.
        val scale = TargetLocator.WORK_SIZE.toFloat() / max(photo.width, photo.height)
        val working = if (scale < 1f) {
            photo.scale((photo.width * scale).roundToInt(), (photo.height * scale).roundToInt())
        } else {
            photo
        }

        val fit = TargetLocator.locate(working.grayscale(), working.width, working.height)
            ?: return null

        val back = 1.0 / (if (scale < 1f) scale.toDouble() else 1.0)
        val full = fit.copy(
            cx = fit.cx * back,
            cy = fit.cy * back,
            major = fit.major * back,
            minor = fit.minor * back,
        )

        val rectified = rectify(photo, full, geometry.blackRatio)
        return TargetPhoto(
            rectified = rectified,
            fit = full,
            sourceWidth = photo.width,
            sourceHeight = photo.height,
            hits = HitDetector.detect(
                rectified = rectified.grayscale(),
                size = CROP_SIZE,
                geometry = geometry,
                frameToScoring = CROP_MARGIN,
            ),
        )
    }

    /**
     * Sample the photo into a square where the target is round and centred.
     *
     * Backwards, from the output: for each destination pixel, ask the fit which
     * source pixel belongs there. Forward mapping would leave gaps wherever the
     * source is stretched.
     */
    internal fun rectify(photo: Bitmap, fit: TargetFit, blackRatio: Double): Bitmap {
        // Both images go through int arrays rather than Bitmap.get/set. Those
        // cross into native code once per pixel, and at 1600² that is five
        // million crossings for one photo — hundreds of milliseconds of nothing
        // but call overhead.
        val source = IntArray(photo.width * photo.height)
        photo.getPixels(source, 0, photo.width, 0, 0, photo.width, photo.height)
        val target = IntArray(CROP_SIZE * CROP_SIZE)

        val half = CROP_SIZE / 2.0
        // The output's half-width corresponds to CROP_MARGIN scoring radii.
        val perPixel = CROP_MARGIN / half

        for (y in 0 until CROP_SIZE) {
            val ny = (y - half) * perPixel
            val row = y * CROP_SIZE
            for (x in 0 until CROP_SIZE) {
                val nx = (x - half) * perPixel
                val (sx, sy) = fit.toImage(nx, ny, blackRatio)
                val ix = sx.roundToInt()
                val iy = sy.roundToInt()
                target[row + x] =
                    if (ix in 0 until photo.width && iy in 0 until photo.height) {
                        source[iy * photo.width + ix]
                    } else {
                        // Outside the photo: black, so a target shot close to
                        // the frame edge is visibly cut off rather than smeared.
                        Color.BLACK
                    }
            }
        }

        val out = createBitmap(CROP_SIZE, CROP_SIZE)
        out.setPixels(target, 0, CROP_SIZE, 0, 0, CROP_SIZE, CROP_SIZE)
        return out
    }
}

/**
 * The aiming mark's diameter as a fraction of ring 1's.
 *
 * The fit measures the mark; everything downstream is expressed against the
 * scoring area, and the ratio between them differs per target — Scheibe Nr. 5
 * is 200/500, air rifle 30.5/45.5.
 */
val TargetGeometry.blackRatio: Double
    get() = blackDiameterMm / ringDiametersMm.last()

/** 8-bit grayscale, row-major — what [TargetLocator] expects. */
internal fun Bitmap.grayscale(): IntArray {
    val pixels = IntArray(width * height)
    getPixels(pixels, 0, width, 0, 0, width, height)
    for (i in pixels.indices) {
        val c = pixels[i]
        val r = (c shr 16) and 0xFF
        val g = (c shr 8) and 0xFF
        val b = c and 0xFF
        // The same luma weights OpenCV uses, so the Kotlin and Python paths
        // threshold identical numbers.
        pixels[i] = (0.299 * r + 0.587 * g + 0.114 * b).toInt()
    }
    return pixels
}

private fun Bitmap.scale(width: Int, height: Int): Bitmap =
    Bitmap.createScaledBitmap(this, width, height, true)
