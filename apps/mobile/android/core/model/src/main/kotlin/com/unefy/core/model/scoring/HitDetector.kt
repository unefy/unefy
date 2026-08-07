package com.unefy.core.model.scoring

import kotlin.math.PI
import kotlin.math.hypot
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sqrt

/** One hole found in a photograph, in the same frame a [ShotInput] uses. */
data class DetectedHit(
    /** Normalised to the scoring radius, origin at the centre, y down. */
    val x: Double,
    val y: Double,
    /**
     * Diameter of the hole's dark core. Reads well under the caliber — see
     * [HitDetector.MIN_HOLE_MM] — but comparably so across one sheet, which is
     * what telling two calibers on one sheet apart needs.
     */
    val diameterMm: Double,
    /** Core brightness over the ink level. Near 0 is a clean hole, 1.0 is print. */
    val tone: Double,
    /** True when the hole was cut out of a clump; its centre is an estimate. */
    val overlapping: Boolean,
) {
    val distance: Double get() = hypot(x, y)
}

/**
 * Finds shot holes in a rectified target crop. Pure Kotlin — no OpenCV, no model.
 *
 * The Kotlin half of a pair, like [TargetLocator]: `ml/scripts/detect_hits.py`
 * does the same job in Python, `ml/scripts/score_hits.py` scores that against
 * holes checked by hand, and [HitDetectorTest] runs both over the same crops so
 * the two cannot drift apart.
 *
 * ## Why there is no model here
 *
 * Because none is needed. Measured against 74 hand-checked holes in real club
 * photographs, this reports 97.4 % precision at 100 % recall. What separates a
 * hole from everything else is local contrast plus one physical fact:
 *
 * > **A hole is darker than the target's own print.**
 *
 * The black of the mark and the black of the printed digits are the same ink; a
 * hole is a shadow into the backstop behind the sheet. Both reference levels —
 * ink and paper — are read off the crop itself, so every threshold below is a
 * ratio and exposure cancels out.
 *
 * That disposes of patches without ever recognising one. A patch is a grey
 * sticker: on paper barely darker than the paper, over the mark lighter than the
 * mark. Neither is darker than ink. So there is no `patch` class and nothing to
 * train — which matters more here than in Python, because it is a ~30 MB native
 * library and a model download that then do not have to ship.
 *
 * ## Where it stops
 *
 * - Two holes overlapping by more than about half a diameter leave no waist
 *   between them and are reported as one.
 * - A fresh hole cannot be told from an old unpatched one. Nothing in a single
 *   photograph can; the club patches after every series and that is the whole
 *   signal (ml/NOTES-real-targets.md §1).
 * - A raised black level — haze, flare, a photograph through glass — breaks the
 *   assumption that exposure cancels out. Plain under- or overexposure does not.
 */
object HitDetector {

    /**
     * How dark a pixel must be, as a fraction of the ink level, to be part of a
     * hole at all. Generous: it decides how far a torn rim is followed, and what
     * survives is decided afterwards on the core.
     */
    const val MASK_TONE = 0.55

    /**
     * How dark a blob's CORE must be, on the same scale, to be a hole.
     *
     * Two thresholds, because what a hole must be told apart from depends on
     * where it lies. On the black mark the competition is the seam between two
     * overlapping patches, which is genuinely dark, so the bar is high. On paper
     * nothing printed is darker than ink at all, and holes there read greyer
     * because what shows through them is the backstop rather than shadow.
     */
    const val MAX_HOLE_TONE = 0.35
    const val MAX_HOLE_TONE_ON_PAPER = 0.60

    /**
     * Ink over paper on a photo the two limits above were tuned on — the median
     * of all 142 crops in the corpus. Both are loosened in proportion when a
     * photo reads flatter than this ([toneSlack]).
     *
     * Hung in front of a BRIGHT, well-lit backstop a hole stops being a shadow —
     * daylight comes through it — and its core reads 0.36 to 0.40 of the ink
     * instead of the usual 0.1. Measured on an S25 photograph from 2026-08-07:
     * five holes found as candidates, every patch on the sheet correctly
     * rejected, and then all five dropped by the 0.35 cut. Nothing reported on a
     * target with five clean hits.
     *
     * This rule is empirical, not derived. How bright the backstop is belongs to
     * the range, and nothing readable off the sheet predicts it — that
     * photograph sits at the 75th percentile of ink/paper, well inside the
     * ordinary spread. What makes it safe is the clamp: the factor may only ever
     * LOOSEN, so no hole found today can be lost, and the labelled corpus scores
     * the same to the last decimal. See detect_hits.py TONE_REFERENCE for the
     * two alternatives that were measured and rejected.
     */
    const val TONE_REFERENCE = 0.346
    const val MAX_TONE_SLACK = 1.5

    /** How far to loosen the tone limits on a flat photo. Never below 1.0. */
    fun toneSlack(ink: Double, paper: Double): Double =
        if (paper <= 0.0) 1.0
        else ((ink / paper) / TONE_REFERENCE).coerceIn(1.0, MAX_TONE_SLACK)

    /**
     * How much darker than its surroundings a candidate must be, as a fraction
     * of the distance from ink to paper. A fraction and not a fixed number of
     * levels: in poor light the whole scale shrinks with it.
     */
    const val MIN_CONTRAST_SPAN = 0.10

    /**
     * Hole sizes worth considering, in millimetres — of the DARK CORE, which is
     * what gets measured and reads well under the caliber. Paper springs back
     * around the projectile and only the properly black part makes the mask:
     * 7.2 mm of core for a 9 mm hole, 3.1 mm for .22, under 2 mm for a grey
     * half-closed hole in paper. Hence a floor nowhere near the 4.5 mm of a
     * diabolo, and a ceiling above .45 for a badly torn one.
     */
    const val MIN_HOLE_MM = 2.0
    const val MAX_HOLE_MM = 14.0

    /** Below this many pixels a blob is sensor noise or a paper fibre. */
    const val MIN_SEED_PX = 8

    /**
     * How round a single hole has to be (4·pi·area / perimeter²). Torn paper is
     * not smooth, so this is loose; it is here to reject the printed ring lines,
     * which are arcs and score far below it. What fails it is not discarded but
     * handed to the splitter, which either finds hole centres in it or does not.
     */
    const val MIN_ROUNDNESS = 0.45

    /**
     * How far apart two hole centres must be, in multiples of the core radius
     * measured on this sheet, to be two holes rather than one torn one. The core
     * reads about three quarters of the caliber, so 1.8 core radii is a little
     * under three quarters of a real diameter.
     */
    const val PITCH = 1.8

    /** How much larger than a hole a blob may be before it is taken for two. */
    const val OVERSIZE = 1.5

    /**
     * Where the ink level is read: an annulus well inside the mark, clear of the
     * light ring-10 core and of the mark's own edge. As fractions of the mark's
     * RADIUS, so the bands land correctly on an air rifle target too, whose
     * black is 30.5 mm and not 200.
     */
    private const val INK_BAND_INNER = 0.35
    private const val INK_BAND_OUTER = 0.85

    /**
     * Where the paper level is read: outside the mark, inside ring 1. The inner
     * edge is a fraction of the mark's radius, the outer of the scoring radius.
     */
    private const val PAPER_BAND_INNER = 1.15
    private const val PAPER_BAND_OUTER = 0.92

    /**
     * Minimum gap between ink and paper, in 8-bit levels. Below it the two
     * anchors mean nothing, and neither would any ratio built on them — a
     * photograph of a wall, or one so flat that nothing can be read from it.
     */
    private const val MIN_ANCHOR_GAP = 30.0

    /** How far around a blob the neighbour ring is sampled, in pixels. */
    private const val RING_INNER_PX = 4
    private const val RING_OUTER_PX = 9

    /**
     * @param rectified 8-bit grayscale square from `TargetPhotoAnalyzer` — the
     *   target centred, [frameToScoring] scoring radii across the half-width.
     * @param geometry the target that was photographed; supplies the scale in
     *   millimetres and where the black sits.
     */
    fun detect(
        rectified: IntArray,
        size: Int,
        geometry: TargetGeometry,
        frameToScoring: Double = TargetGeometry.FRAME_TO_SCORING,
    ): List<DetectedHit> {
        require(rectified.size == size * size) {
            "expected a square image of ${size * size} pixels, got ${rectified.size}"
        }

        val scoringRadiusMm = geometry.scoringRadiusMm
        val pxPerMm = size / (2.0 * frameToScoring * scoringRadiusMm)
        val markRadiusPx = geometry.blackDiameterMm / 2.0 * pxPerMm
        val scoringRadiusPx = scoringRadiusMm * pxPerMm

        val ink = bandMedian(
            rectified, size,
            INK_BAND_INNER * markRadiusPx,
            INK_BAND_OUTER * markRadiusPx,
        ) ?: return emptyList()
        val paper = bandMedian(
            rectified, size,
            PAPER_BAND_INNER * markRadiusPx,
            PAPER_BAND_OUTER * scoringRadiusPx,
        ) ?: return emptyList()
        if (paper - ink < MIN_ANCHOR_GAP) return emptyList()

        val blurred = blur(rectified, size)
        val contrast = localContrast(blurred, size, pxPerMm)

        // Nothing is looked for outside ring 1. The crop reaches past it, but so
        // does the edge of the sheet and the backstop behind it, and neither is
        // a shot.
        val contrastFloor = MIN_CONTRAST_SPAN * (paper - ink)
        val toneCeiling = ink * MASK_TONE
        val centre = (size - 1) / 2.0
        val seeds = BooleanArray(rectified.size)
        for (y in 0 until size) {
            val dy = y - centre
            val row = y * size
            for (x in 0 until size) {
                val dx = x - centre
                if (dx * dx + dy * dy > scoringRadiusPx * scoringRadiusPx) continue
                val i = row + x
                seeds[i] = contrast[i] >= contrastFloor && blurred[i] <= toneCeiling
            }
        }

        return measure(
            image = rectified,
            mask = open(seeds, size),
            size = size,
            pxPerMm = pxPerMm,
            centre = centre,
            ink = ink,
            paper = paper,
            scoringRadiusMm = scoringRadiusMm,
        )
    }

    // --- Deciding what each blob is ---

    private class Blob(
        val pixels: IntArray,
        val x: Double,
        val y: Double,
        val radiusPx: Double,
        val tone: Double,
    )

    private class Peak(val x: Double, val y: Double, val radius: Double)

    private fun measure(
        image: IntArray,
        mask: BooleanArray,
        size: Int,
        pxPerMm: Double,
        centre: Double,
        ink: Double,
        paper: Double,
        scoringRadiusMm: Double,
    ): List<DetectedHit> {
        // Eight-connected, unlike the sheet masks in TargetLocator: the black of
        // a torn hole breaks into fragments that touch only at their corners,
        // and four-connectivity reports each fragment as a hole of its own.
        val labelling = TargetLocator.label(mask, size, size, diagonal = true)
        val byLabel = pixelsByLabel(labelling)
        val paperSide = (ink + paper) / 2.0
        val slack = toneSlack(ink, paper)
        val onMarkLimit = MAX_HOLE_TONE * slack
        val onPaperLimit = MAX_HOLE_TONE_ON_PAPER * slack

        val singles = mutableListOf<Blob>()
        val clumps = mutableListOf<Blob>()

        for (label in 1..labelling.count) {
            val area = labelling.areas[label]
            if (area < MIN_SEED_PX) continue
            val diameterMm = 2.0 * sqrt(area / PI) / pxPerMm
            if (diameterMm < MIN_HOLE_MM) continue

            val pixels = byLabel[label]
            val (inner, outer) = coreAndRing(image, pixels, size)
            val tone = if (ink > 0) inner / ink else 1.0
            if (tone > (if (outer >= paperSide) onPaperLimit else onMarkLimit)) {
                continue
            }

            var sumX = 0.0
            var sumY = 0.0
            for (index in pixels) {
                sumX += index % size
                sumY += index / size
            }
            val blob = Blob(
                pixels = pixels,
                x = sumX / area,
                y = sumY / area,
                radiusPx = diameterMm / 2 * pxPerMm,
                tone = tone,
            )

            // A single hole has to look like one: round enough, and no wider
            // than a .45. Anything else is either several holes that touch — a
            // pair 7 mm apart is one connected region, and pairs are what a good
            // series produces — or not a hole at all. Both go to the splitter,
            // which answers the question by finding centres in it or not.
            if (diameterMm <= MAX_HOLE_MM && roundness(pixels, size, area) >= MIN_ROUNDNESS) {
                singles.add(blob)
            } else {
                clumps.add(blob)
            }
        }

        // How big a hole is on THIS sheet, taken from the ones nothing had to be
        // assumed about. It is what the splitter needs, and it is why the same
        // clump is one torn .45 hole here and three diabolo holes there.
        val expectedR = if (singles.isEmpty()) {
            MIN_HOLE_MM / 2 * pxPerMm
        } else {
            singles.map { it.radiusPx }.sorted()[singles.size / 2]
        }
        val minRadius = MIN_HOLE_MM / 2 * pxPerMm

        val hits = mutableListOf<DetectedHit>()

        fun emit(x: Double, y: Double, radiusPx: Double, tone: Double, overlapping: Boolean) {
            val diameterMm = 2 * radiusPx / pxPerMm
            if (diameterMm < MIN_HOLE_MM || diameterMm > MAX_HOLE_MM) return
            hits.add(
                DetectedHit(
                    x = (x - centre) / pxPerMm / scoringRadiusMm,
                    y = (y - centre) / pxPerMm / scoringRadiusMm,
                    diameterMm = diameterMm,
                    tone = tone,
                    overlapping = overlapping,
                ),
            )
        }

        for (blob in singles) {
            // Two holes side by side make a shape round enough to have passed as
            // one, and only its size gives it away.
            val parts = if (blob.radiusPx > OVERSIZE * expectedR) {
                split(blob.pixels, size, expectedR, minRadius)
            } else {
                emptyList()
            }
            if (parts.size > 1) {
                parts.forEach { emit(it.x, it.y, it.radius, blob.tone, true) }
            } else {
                emit(blob.x, blob.y, blob.radiusPx, blob.tone, false)
            }
        }
        for (blob in clumps) {
            val parts = split(blob.pixels, size, expectedR, minRadius)
            parts.forEach { emit(it.x, it.y, it.radius, blob.tone, parts.size > 1) }
        }

        return hits.sortedBy { it.distance }
    }

    /**
     * Brightness of a blob's core, and of the ring of neighbours around it.
     *
     * The median of the core, and nothing lower: a torn hole has flaps of paper
     * standing up inside it that catch the light and pull the median towards
     * grey, so a low percentile looks like the fairer statistic — measured
     * against the hand-checked holes it cost precision and found nothing.
     */
    private fun coreAndRing(image: IntArray, pixels: IntArray, size: Int): Pair<Double, Double> {
        val blob = HashSet<Int>(pixels.size * 2)
        for (index in pixels) blob.add(index)

        // The core: blob pixels whose four neighbours are also in the blob — the
        // erosion by the 3x3 cross that OpenCV builds at that size.
        val core = pixels.filter { index ->
            val x = index % size
            val y = index / size
            x > 0 && x < size - 1 && y > 0 && y < size - 1 &&
                blob.contains(index - 1) && blob.contains(index + 1) &&
                blob.contains(index - size) && blob.contains(index + size)
        }
        val inner = median(image, if (core.size >= 4) core.toIntArray() else pixels)

        val near = stamp(pixels, size, RING_INNER_PX)
        val far = stamp(pixels, size, RING_OUTER_PX)
        val band = far.filterNot { near.contains(it) }
        val outer = if (band.isEmpty()) inner else median(image, band.toIntArray())
        return inner to outer
    }

    /**
     * Perimeter-based roundness, 1.0 for a circle.
     *
     * The perimeter is traced around the outer boundary counting a diagonal step
     * as √2, which is what OpenCV's `arcLength` over a chain code does. The two
     * implementations have to agree on this number, because it decides which
     * blobs are handed to the splitter.
     */
    private fun roundness(pixels: IntArray, size: Int, area: Int): Double {
        val perimeter = tracePerimeter(pixels, size)
        if (perimeter <= 0.0) return 0.0
        return 4.0 * PI * area / (perimeter * perimeter)
    }

    /**
     * Pull the individual holes out of a clump of touching ones.
     *
     * Two holes 7 mm apart are one connected region, and reporting that as one
     * big hole loses a shot and invents a nonsense size. The distance transform
     * peaks where a hole is roundest and deepest, so its local maxima are the
     * candidate centres and the peak value is that hole's radius.
     *
     * The limit is geometric rather than a matter of tuning: past roughly half a
     * diameter of overlap there is no waist left between two holes, and they are
     * then indistinguishable from one larger hole, for this and for anything
     * else.
     */
    private fun split(
        pixels: IntArray,
        size: Int,
        expectedR: Double,
        minRadius: Double,
    ): List<Peak> {
        var minX = size
        var maxX = 0
        var minY = size
        var maxY = 0
        for (index in pixels) {
            val x = index % size
            val y = index / size
            minX = min(minX, x)
            maxX = max(maxX, x)
            minY = min(minY, y)
            maxY = max(maxY, y)
        }
        // A pixel of background all round, so the transform sees the edge.
        val pad = 1
        val boxW = maxX - minX + 1 + 2 * pad
        val boxH = maxY - minY + 1 + 2 * pad
        val inside = BooleanArray(boxW * boxH)
        for (index in pixels) {
            val x = index % size - minX + pad
            val y = index / size - minY + pad
            inside[y * boxW + x] = true
        }

        val distance = distanceTransform(inside, boxW, boxH)
        val pitch = PITCH * expectedR
        val window = max(1, (pitch / 2).toInt())

        val candidates = mutableListOf<Peak>()
        for (y in 0 until boxH) {
            for (x in 0 until boxW) {
                val value = distance[y * boxW + x]
                if (value < minRadius) continue
                if (!isLocalMax(distance, boxW, boxH, x, y, window, value)) continue
                candidates.add(
                    Peak(
                        x = (x - pad + minX).toDouble(),
                        y = (y - pad + minY).toDouble(),
                        radius = value,
                    ),
                )
            }
        }

        // Widest first, and drop whatever falls inside a hole already taken.
        val kept = mutableListOf<Peak>()
        for (peak in candidates.sortedByDescending { it.radius }) {
            if (kept.none { hypot(peak.x - it.x, peak.y - it.y) < pitch }) kept.add(peak)
        }
        return kept
    }

    private fun isLocalMax(
        distance: DoubleArray,
        width: Int,
        height: Int,
        x: Int,
        y: Int,
        window: Int,
        value: Double,
    ): Boolean {
        for (dy in -window..window) {
            val ny = y + dy
            if (ny < 0 || ny >= height) continue
            val row = ny * width
            for (dx in -window..window) {
                val nx = x + dx
                if (nx < 0 || nx >= width) continue
                if (distance[row + nx] > value + 1e-6) return false
            }
        }
        return true
    }

    // --- The image operations that OpenCV would otherwise provide ---

    /** Median brightness in a ring around the centre, or null if it is empty. */
    private fun bandMedian(
        image: IntArray,
        size: Int,
        innerPx: Double,
        outerPx: Double,
    ): Double? {
        val centre = (size - 1) / 2.0
        val inner = innerPx * innerPx
        val outer = outerPx * outerPx
        val histogram = IntArray(256)
        var count = 0
        for (y in 0 until size) {
            val dy = y - centre
            val row = y * size
            for (x in 0 until size) {
                val dx = x - centre
                val squared = dx * dx + dy * dy
                if (squared < inner || squared > outer) continue
                histogram[image[row + x].coerceIn(0, 255)]++
                count++
            }
        }
        return medianOf(histogram, count)
    }

    private fun median(image: IntArray, pixels: IntArray): Double {
        val histogram = IntArray(256)
        for (index in pixels) histogram[image[index].coerceIn(0, 255)]++
        return medianOf(histogram, pixels.size) ?: 0.0
    }

    /**
     * The value at the half-way point of a histogram.
     *
     * NumPy averages the two middle values of an even-sized sample and this
     * takes the upper one, a difference of at most half a grey level on samples
     * of thousands of pixels — far below anything the thresholds react to.
     */
    private fun medianOf(histogram: IntArray, count: Int): Double? {
        if (count == 0) return null
        val half = count / 2
        var seen = 0
        for (value in 0..255) {
            seen += histogram[value]
            if (seen > half) return value.toDouble()
        }
        return 255.0
    }

    /**
     * The pixels of every label, in one pass.
     *
     * Per label it would be one pass each: at two and a half million pixels and
     * twenty blobs that is fifty million comparisons to find a few thousand
     * pixels, and it was measurable on the phone.
     */
    private fun pixelsByLabel(labelling: TargetLocator.Labelling): Array<IntArray> {
        val out = Array(labelling.count + 1) { IntArray(labelling.areas[it]) }
        val at = IntArray(labelling.count + 1)
        val labels = labelling.labels
        for (index in labels.indices) {
            val label = labels[index]
            if (label == 0) continue
            out[label][at[label]++] = index
        }
        return out
    }

    /** Every pixel within [radius] of any of [pixels] — a disk dilation. */
    private fun stamp(pixels: IntArray, size: Int, radius: Int): HashSet<Int> {
        val out = HashSet<Int>(pixels.size * 4)
        val offsets = diskOffsets(radius, size)
        for (index in pixels) {
            val x = index % size
            val y = index / size
            for ((dx, dy) in offsets) {
                val nx = x + dx
                val ny = y + dy
                if (nx in 0 until size && ny in 0 until size) out.add(ny * size + nx)
            }
        }
        return out
    }

    private val diskCache = HashMap<Int, List<Pair<Int, Int>>>()

    /** The disk OpenCV rasterises for an ellipse element of this radius. */
    private fun diskOffsets(radius: Int, size: Int): List<Pair<Int, Int>> =
        diskCache.getOrPut(radius) {
            val offsets = mutableListOf<Pair<Int, Int>>()
            for (dy in -radius..radius) {
                val dx = sqrt((radius * radius - dy * dy).toDouble()).toInt()
                for (x in -dx..dx) offsets.add(x to dy)
            }
            offsets
        }

    /** 3x3 Gaussian, separable [1 2 1]/4 — the kernel OpenCV uses at ksize 3. */
    private fun blur(image: IntArray, size: Int): IntArray {
        val horizontal = IntArray(image.size)
        for (y in 0 until size) {
            val row = y * size
            for (x in 0 until size) {
                val left = image[row + max(0, x - 1)]
                val right = image[row + min(size - 1, x + 1)]
                horizontal[row + x] = (left + 2 * image[row + x] + right + 2) / 4
            }
        }
        val out = IntArray(image.size)
        for (y in 0 until size) {
            val up = max(0, y - 1) * size
            val down = min(size - 1, y + 1) * size
            val row = y * size
            for (x in 0 until size) {
                out[row + x] =
                    (horizontal[up + x] + 2 * horizontal[row + x] + horizontal[down + x] + 2) / 4
            }
        }
        return out
    }

    /**
     * How much darker each pixel is than its own surroundings.
     *
     * Closing with a shape wider than any hole paints the hole over with
     * whatever it sits on — mark, paper or an old patch — so the difference is
     * the hole's depth alone, background subtracted. Everything downstream works
     * on depth rather than brightness, which is what lets one set of thresholds
     * hold on black and on white at once.
     *
     * A square, where the Python reference began with a disk: a square is
     * separable, so this is four linear passes rather than one that is quadratic
     * in the kernel — at 50 pixels across, the difference between milliseconds
     * and minutes. Scored against the hand-checked holes the two are
     * indistinguishable, and Python uses the square as well now.
     */
    private fun localContrast(blurred: IntArray, size: Int, pxPerMm: Double): IntArray {
        val side = max(3, (1.4 * MAX_HOLE_MM * pxPerMm).toInt() or 1)
        val radius = side / 2
        val closed = extremeFilter(extremeFilter(blurred, size, radius, true), size, radius, false)
        return IntArray(blurred.size) { max(0, closed[it] - blurred[it]) }
    }

    /**
     * Square max or min filter, horizontally then vertically.
     *
     * A sliding window extreme by way of a monotonic deque: each pixel enters
     * and leaves once, so the cost does not grow with the window. The naive
     * version is 2500 comparisons per pixel at this kernel size, which on a
     * 1600² crop is minutes.
     */
    private fun extremeFilter(
        image: IntArray,
        size: Int,
        radius: Int,
        maximum: Boolean,
    ): IntArray {
        val horizontal = IntArray(image.size)
        val deque = IntArray(size)
        for (y in 0 until size) {
            val row = y * size
            slide(image, row, 1, size, radius, maximum, deque, horizontal, row, 1)
        }
        val out = IntArray(image.size)
        for (x in 0 until size) {
            slide(horizontal, x, size, size, radius, maximum, deque, out, x, size)
        }
        return out
    }

    private fun slide(
        source: IntArray,
        start: Int,
        stride: Int,
        length: Int,
        radius: Int,
        maximum: Boolean,
        deque: IntArray,
        target: IntArray,
        targetStart: Int,
        targetStride: Int,
    ) {
        var head = 0
        var tail = 0
        var next = 0
        for (i in 0 until length) {
            // Everything within reach of position i has entered the window.
            while (next <= i + radius && next < length) {
                val value = source[start + next * stride]
                while (tail > head) {
                    val back = source[start + deque[tail - 1] * stride]
                    val worse = if (maximum) back <= value else back >= value
                    if (!worse) break
                    tail--
                }
                deque[tail++] = next
                next++
            }
            while (deque[head] < i - radius) head++
            target[targetStart + i * targetStride] = source[start + deque[head] * stride]
        }
    }

    /** Opening with the 3x3 cross OpenCV builds at that size: erode, then dilate. */
    private fun open(mask: BooleanArray, size: Int): BooleanArray {
        val eroded = BooleanArray(mask.size)
        for (y in 1 until size - 1) {
            val row = y * size
            for (x in 1 until size - 1) {
                val i = row + x
                if (!mask[i]) continue
                eroded[i] = mask[i - 1] && mask[i + 1] && mask[i - size] && mask[i + size]
            }
        }
        val out = BooleanArray(mask.size)
        for (y in 0 until size) {
            val row = y * size
            for (x in 0 until size) {
                val i = row + x
                if (!eroded[i]) continue
                out[i] = true
                if (y > 0) out[i - size] = true
                if (y < size - 1) out[i + size] = true
                if (x > 0) out[i - 1] = true
                if (x < size - 1) out[i + 1] = true
            }
        }
        return out
    }

    /**
     * Exact Euclidean distance to the nearest background pixel.
     *
     * Felzenszwalb and Huttenlocher's lower envelope, one dimension at a time —
     * exact, and linear in the number of pixels. A chamfer approximation was the
     * alternative and is several per cent off, which is enough to move a hole
     * centre when the peak it is taken from is only a few pixels across.
     */
    internal fun distanceTransform(inside: BooleanArray, width: Int, height: Int): DoubleArray {
        val infinity = 1e12
        val squared = DoubleArray(inside.size) { if (inside[it]) infinity else 0.0 }

        val length = max(width, height)
        val line = DoubleArray(length)
        val envelope = DoubleArray(length + 1)
        val boundary = IntArray(length + 1)
        val result = DoubleArray(length)

        for (x in 0 until width) {
            for (y in 0 until height) line[y] = squared[y * width + x]
            transform1d(line, height, envelope, boundary, result)
            for (y in 0 until height) squared[y * width + x] = result[y]
        }
        for (y in 0 until height) {
            val row = y * width
            for (x in 0 until width) line[x] = squared[row + x]
            transform1d(line, width, envelope, boundary, result)
            for (x in 0 until width) squared[row + x] = result[x]
        }

        return DoubleArray(squared.size) { sqrt(squared[it]) }
    }

    private fun transform1d(
        line: DoubleArray,
        length: Int,
        envelope: DoubleArray,
        boundary: IntArray,
        out: DoubleArray,
    ) {
        var rightmost = 0
        boundary[0] = 0
        envelope[0] = -1e20
        envelope[1] = 1e20

        for (q in 1 until length) {
            var s: Double
            while (true) {
                val p = boundary[rightmost]
                s = ((line[q] + q.toDouble() * q) - (line[p] + p.toDouble() * p)) /
                    (2.0 * q - 2.0 * p)
                if (s > envelope[rightmost]) break
                rightmost--
            }
            rightmost++
            boundary[rightmost] = q
            envelope[rightmost] = s
            envelope[rightmost + 1] = 1e20
        }

        var at = 0
        for (q in 0 until length) {
            while (envelope[at + 1] < q) at++
            val p = boundary[at]
            val d = (q - p).toDouble()
            out[q] = d * d + line[p]
        }
    }

    /**
     * Length of the outer boundary, walked pixel by pixel.
     *
     * Moore-neighbour tracing: from the topmost-leftmost pixel, keep the
     * background on the left and step around the shape, counting an orthogonal
     * step as 1 and a diagonal as √2. That is the same sum OpenCV's `arcLength`
     * takes over a chain-coded contour, which is what makes the roundness of the
     * two implementations comparable.
     */
    internal fun tracePerimeter(pixels: IntArray, size: Int): Double {
        val blob = HashSet<Int>(pixels.size * 2)
        for (index in pixels) blob.add(index)

        val start = pixels.min()
        val startX = start % size
        val startY = start / size

        // Clockwise from due west. West is where the walk starts looking,
        // because the topmost-leftmost pixel of a blob has background there by
        // construction — that is what makes it the topmost-leftmost.
        val dx = intArrayOf(-1, -1, 0, 1, 1, 1, 0, -1)
        val dy = intArrayOf(0, -1, -1, -1, 0, 1, 1, 1)

        fun solid(x: Int, y: Int): Boolean =
            x in 0 until size && y in 0 until size && blob.contains(y * size + x)

        var x = startX
        var y = startY
        // Where to resume the clockwise sweep: one step on from the pixel the
        // walk arrived from. Searching from the arrival direction is what keeps
        // it on the boundary instead of cutting through the middle.
        var search = 1
        var firstStep = -1
        var perimeter = 0.0
        var steps = 0
        val limit = 8 * pixels.size + 16

        while (steps < limit) {
            var direction = -1
            for (turn in 0 until 8) {
                val d = (search + turn) % 8
                if (solid(x + dx[d], y + dy[d])) {
                    direction = d
                    break
                }
            }
            // A single pixel with nothing next to it has no boundary to walk.
            if (direction < 0) return 0.0

            // Jacob's criterion: standing on the start pixel about to repeat the
            // first step means the loop has closed. Arriving at the start is not
            // enough on its own — a shape pinched to one pixel wide is passed
            // through twice on the way round.
            if (steps > 0 && x == startX && y == startY && direction == firstStep) break
            if (steps == 0) firstStep = direction

            perimeter += if (direction % 2 == 0) 1.0 else SQRT2
            x += dx[direction]
            y += dy[direction]
            // The pixel just left is now the one behind: resume one step
            // clockwise of it.
            search = (direction + 5) % 8
            steps++
        }
        return perimeter
    }

    private val SQRT2 = sqrt(2.0)
}
