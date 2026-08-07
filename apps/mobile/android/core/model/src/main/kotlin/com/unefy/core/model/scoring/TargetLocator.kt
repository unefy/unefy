package com.unefy.core.model.scoring

import kotlin.math.abs
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.hypot
import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt
import kotlin.math.sin
import kotlin.math.sqrt

/**
 * Finds the shooting target in a photo. Pure Kotlin — no OpenCV, no Android.
 *
 * The Kotlin half of a pair, like [ScoringEngine]: `ml/scripts/rectify.py` does
 * the same job in Python and is the reference this is checked against
 * ([TargetLocatorTest] runs both over the same photographs). Keeping it free of
 * native code avoids shipping a ~30 MB library and the 16 KB page-alignment
 * problem that comes with one at targetSdk 36.
 *
 * ## Why geometry rather than a neural network
 *
 * A circle photographed at an angle is an ellipse. The black aiming mark is the
 * highest-contrast feature on any target and its physical diameter is fixed per
 * target type, so fitting an ellipse to it yields centre, scale (px→mm) and
 * perspective in one step — deterministically and without training data. A model
 * is only needed later, to tell holes from patches.
 *
 * ## What real photographs forced
 *
 * Measured over 142 club photos; both of these produced confident nonsense
 * rather than an error, which is why the checks exist (ml/NOTES-real-targets.md):
 *
 * - **The backstop joins the sheet.** One threshold splits "target and backstop"
 *   from "dark surroundings", and the grey foam board lands with the paper.
 *   Being darker than paper it then becomes the biggest dark region *inside* the
 *   sheet, and the fit lands on the backstop. Hence the second threshold pass.
 * - **Nothing bounded the size.** A "mark" 1.56× the width of the whole sheet
 *   was accepted. Hence [MIN_MARK_OF_SHEET]/[MAX_MARK_OF_SHEET].
 *
 * The aiming mark is also an *annulus* — ring 10 is printed light inside it — so
 * regions get their holes filled before measuring. Fitting the inner boundary
 * would be wrong by a factor of four in scale.
 */
object TargetLocator {

    /** Longest edge the analysis runs at. Bigger costs time and finds nothing new. */
    const val WORK_SIZE = 1024

    /** Plausible mark diameter as a fraction of the sheet's width. */
    const val MIN_MARK_OF_SHEET = 0.08
    const val MAX_MARK_OF_SHEET = 0.65

    /** Below this the photo is too oblique to trust the affine rectification. */
    const val OBLIQUE_WARN = 0.80

    /**
     * How far the paper's brightness may fall before the sheet is taken to have
     * ended. Well below the paper, because a sheet is never evenly lit; well
     * above the grey of a backstop.
     */
    private const val SHEET_EDGE_OF_PAPER = 0.72

    /**
     * How many directions the sheet's edge is probed in, and how far out, in
     * multiples of the mark's radius. The sheet reaches three mark radii to its
     * edge and 4.2 to its corners, so five leaves room for an oblique photo.
     */
    private const val SHEET_RAYS = 180
    private const val SHEET_REACH = 5.0

    /** See [sheetEdgePoints]. Must stay above the 1.41 of a square's corner. */
    private const val SHEET_RAY_TRIM = 1.7

    /** How much of a region's fitted ellipse must actually be filled. */
    private const val MIN_FILL = 0.75

    /** A region below this many pixels is noise, not an aiming mark. */
    private const val MIN_REGION_PX = 500

    /** A sheet has to be a substantial part of the frame — but not all of it. */
    private const val MIN_SHEET_AREA = 0.10
    private const val MAX_SHEET_AREA = 0.95

    /**
     * How round the mark must look before a live frame is believed.
     *
     * Set from the data, not from caution: across 142 club photographs the least
     * circular fit was 0.96, because people photograph targets from the front.
     * 0.85 leaves room for a phone held at an angle while ruling out the
     * squashed blobs — shadows, door frames, the edge of a bench — that an
     * earlier 0.55 waved through. A genuinely oblique shot is better retaken
     * than measured anyway.
     */
    private const val LIVE_MIN_CIRCULARITY = 0.85

    /** How much of the frame the sheet must fill before a live frame is believed. */
    private const val LIVE_MIN_SHEET_AREA = 0.15

    /** How far off centre the mark may sit in a live frame. */
    private const val LIVE_MAX_OFF_CENTRE = 0.30

    /**
     * How far the mark may sit from the middle of the SHEET, as a fraction of
     * the sheet's size.
     *
     * Measured across 142 club photographs: median 0.074, worst 0.183. A printed
     * target has its mark in the middle, so anything further out means the mask
     * is not a sheet. This is what catches a pale backstop being swallowed along
     * with the paper — the combined blob's centre sits well above the mark, and
     * nothing else noticed.
     */
    private const val LIVE_MAX_MARK_OFFSET = 0.22

    /**
     * How much of its own bounding box the sheet mask must fill.
     *
     * Same measurements: median 0.915, worst 0.761. A sheet is a rectangle; a
     * mask that only loosely fills its box has swallowed something else.
     */
    private const val LIVE_MIN_RECTANGULARITY = 0.70

    /**
     * Minimum brightness gap between paper and aiming mark, in 8-bit levels.
     *
     * Everything else here is relative, which is what a threshold should be —
     * but "relative" also means a dark patch on a mid-grey wall looks exactly
     * like a mark on paper. Printed targets are near-white against near-black;
     * anything with less separation than this is not one, whatever the exposure.
     */
    private const val LIVE_MIN_CONTRAST = 70.0

    /**
     * @param pixels 8-bit grayscale, row-major, `width * height` entries.
     * @param strict for the live viewfinder. A still photo is deliberate — the
     *   user framed a target and pressed a button, so guessing is worth it. A
     *   preview frame is whatever the camera happens to be pointing at, most of
     *   which is not a target at all, and a lenient search finds a "target" in a
     *   doorway or a shadow and then fires the shutter at it.
     */
    fun locate(
        pixels: IntArray,
        width: Int,
        height: Int,
        strict: Boolean = false,
    ): TargetFit? {
        require(pixels.size == width * height) {
            "expected ${width * height} pixels, got ${pixels.size}"
        }

        val sheet = findSheet(pixels, width, height)
        if (strict) {
            // No sheet, no target. The fallback below exists for a photograph
            // whose sheet mask came out wrong; in a preview stream it is the
            // single biggest source of false positives.
            if (sheet == null) return null
            if (sheet.count { it } < LIVE_MIN_SHEET_AREA * pixels.size) return null

            val fit = findAimingMark(pixels, width, height, sheet) ?: return null
            if (fit.circularity < LIVE_MIN_CIRCULARITY) return null
            if (contrast(pixels, width, sheet, fit) < LIVE_MIN_CONTRAST) return null
            if (!markSitsOnSheet(sheet, width, height, fit)) return null
            // The mark must be near the middle of what was framed; a dark corner
            // of the room is not the target somebody is aiming at.
            val offCentre = kotlin.math.hypot(fit.cx - width / 2.0, fit.cy - height / 2.0)
            if (offCentre > LIVE_MAX_OFF_CENTRE * minOf(width, height)) return null
            return fit
        }

        return findAimingMark(pixels, width, height, sheet)
            // The sheet mask can be wrong — a bright wall, an overexposed
            // backstop. Worth one retry without it before giving up.
            ?: if (sheet != null) findAimingMark(pixels, width, height, null) else null
    }

    /**
     * How far apart paper and mark are in brightness.
     *
     * Sampled from the mark's own interior against the rest of the sheet, rather
     * than from the whole frame: the surroundings say nothing about whether what
     * was found is printed on paper.
     */
    private fun contrast(
        pixels: IntArray,
        width: Int,
        sheet: BooleanArray,
        fit: TargetFit,
    ): Double {
        var markSum = 0.0
        var markCount = 0
        var paperSum = 0.0
        var paperCount = 0
        // Well inside the mark, so a soft edge does not muddy the reading.
        val inner = fit.minor * 0.6

        for (i in pixels.indices) {
            if (!sheet[i]) continue
            val x = i % width
            val y = i / width
            val distance = hypot(x - fit.cx, y - fit.cy)
            when {
                distance <= inner -> { markSum += pixels[i]; markCount++ }
                distance > fit.major * 1.4 -> { paperSum += pixels[i]; paperCount++ }
            }
        }
        if (markCount == 0 || paperCount == 0) return 0.0
        return (paperSum / paperCount) - (markSum / markCount)
    }

    /**
     * Whether the mark sits in the middle of a sheet-shaped mask.
     *
     * Two checks in one, both from the same measurements: the mark near the
     * centre, and the mask actually rectangular. Either alone lets the failure
     * through where a light-coloured backstop merges with the paper.
     */
    private fun markSitsOnSheet(
        sheet: BooleanArray,
        width: Int,
        height: Int,
        fit: TargetFit,
    ): Boolean {
        var minX = width
        var maxX = -1
        var minY = height
        var maxY = -1
        var area = 0
        for (i in sheet.indices) {
            if (!sheet[i]) continue
            area++
            val x = i % width
            val y = i / width
            if (x < minX) minX = x
            if (x > maxX) maxX = x
            if (y < minY) minY = y
            if (y > maxY) maxY = y
        }
        if (maxX < minX || maxY < minY) return false

        val boxWidth = (maxX - minX).toDouble()
        val boxHeight = (maxY - minY).toDouble()
        if (boxWidth <= 0 || boxHeight <= 0) return false

        if (area / (boxWidth * boxHeight) < LIVE_MIN_RECTANGULARITY) return false

        val offsetX = abs(fit.cx - (minX + maxX) / 2.0) / boxWidth
        val offsetY = abs(fit.cy - (minY + maxY) / 2.0) / boxHeight
        return max(offsetX, offsetY) <= LIVE_MAX_MARK_OFFSET
    }

    // --- Step 1: the paper ---

    /**
     * The bright sheet as a mask, if one stands out.
     *
     * Never used for measuring: sheet formats vary by manufacturer while the
     * aiming mark is standardised, so scale always comes from the mark. This
     * only narrows *where* to look.
     */
    internal fun findSheet(pixels: IntArray, width: Int, height: Int): BooleanArray? {
        val level = otsu(pixels)
        var mask = BooleanArray(pixels.size) { pixels[it] > level }

        // Second split over the bright side alone, to separate paper from the
        // grey backstop that the first split kept.
        val upper = pixels.filter { it > level }.toIntArray()
        if (upper.isNotEmpty()) {
            val paperLevel = otsu(upper)
            val refined = BooleanArray(pixels.size) { pixels[it] > paperLevel }
            val refinedCount = refined.count { it }
            // The second pass may only NARROW the mask. On uniformly bright
            // paper there is nothing left to split, Otsu returns 0, and
            // "brighter than 0" is the whole image — which was then taken for
            // the sheet. It also must not narrow it to nothing.
            if (refinedCount > 0.06 * pixels.size && refinedCount < mask.count { it }) {
                mask = refined
            }
        }

        val labelling = label(mask, width, height)
        val biggest = (1..labelling.count).maxByOrNull { labelling.areas[it] } ?: return null
        if (labelling.areas[biggest] < MIN_SHEET_AREA * pixels.size) return null
        // An upper bound as well as a lower one. On a featureless frame — a
        // blank wall, a lens cap, an evenly lit floor — the threshold has
        // nothing to separate and everything comes out "bright", which was
        // happily accepted as a sheet covering the entire image.
        if (labelling.areas[biggest] > MAX_SHEET_AREA * pixels.size) return null

        // Filled: the sheet is punched full of holes, and its own shot holes
        // must not become part of its boundary.
        return fillHoles(labelling.maskOf(biggest), width, height)
    }

    /**
     * The sheet's four corners, for the viewfinder's framing outline.
     *
     * Deliberately the SHEET and not the aiming mark. Live detection first tried
     * the mark, and it was hopeless: a small ellipse fitted to a 480x360 preview
     * frame jitters, squashes and jumps between candidates. The sheet is a large
     * high-contrast rectangle — stable in the same frame, and a quadrilateral
     * cannot deform into something absurd the way an ellipse can.
     *
     * Corners come from the extremes of `x+y` and `x-y`, the standard trick for
     * document scanning: no contour tracing needed, and it copes with the sheet
     * being rotated in frame.
     */
    /**
     * The outline to draw in the viewfinder: the square that rectifying will
     * cut out, or null when there is no aiming mark to measure it from.
     *
     * See [TargetFit.cropOutline] for why this, and not the sheet's own edge.
     */
    fun findCropOutline(
        pixels: IntArray,
        width: Int,
        height: Int,
        blackRatio: Double,
    ): SheetQuad? =
        findAimingMark(pixels, width, height, findSheet(pixels, width, height))
            ?.cropOutline(width, height, blackRatio)

    fun findSheetQuad(pixels: IntArray, width: Int, height: Int): SheetQuad? {
        require(pixels.size == width * height) {
            "expected ${width * height} pixels, got ${pixels.size}"
        }

        // The outline starts from the aiming mark, not from a brightness mask.
        // Measured over 142 club photographs against the sheet's own geometry —
        // the mark is standardised, so half the sheet's width over the mark's
        // radius is a constant of the printed sheet, and it is 3.00 for these:
        //
        //     brightness threshold   2.68   eleven per cent short, every time
        //     rays from the mark     3.02
        //
        // The threshold falls short because it is a threshold. The lower part
        // of a sheet is nearly always in shadow, a global split puts it on the
        // wrong side, and the outline then cuts straight across the target —
        // which it did on three of four real photographs. Gradients do not care
        // about a shadow, which is what document scanners use; but a scanner
        // has to find a sheet in an unknown scene, and by this point we already
        // know exactly where the target is and how big it is.
        //
        // The cost is that no mark means no outline. That is the right answer
        // for a viewfinder anyway: a green frame around something that is not a
        // target is worse than no frame.
        val fit = findAimingMark(pixels, width, height, findSheet(pixels, width, height))
            ?: return null
        val hull = convexHull(sheetEdgePoints(pixels, width, height, fit))
        if (hull.size < 3) return null

        var minSum = Int.MAX_VALUE
        var maxSum = Int.MIN_VALUE
        var minDiff = Int.MAX_VALUE
        var maxDiff = Int.MIN_VALUE
        var topLeft = hull.first()
        var bottomRight = hull.first()
        var topRight = hull.first()
        var bottomLeft = hull.first()

        for (point in hull) {
            val (x, y) = point
            val sum = x + y
            val diff = x - y
            if (sum < minSum) { minSum = sum; topLeft = point }
            if (sum > maxSum) { maxSum = sum; bottomRight = point }
            if (diff > maxDiff) { maxDiff = diff; topRight = point }
            if (diff < minDiff) { minDiff = diff; bottomLeft = point }
        }

        // Area from the quadrilateral, not the mask: the outline is what the
        // user sees, so "close enough" should mean what it encloses.
        val area = polygonArea(listOf(topLeft, topRight, bottomRight, bottomLeft))
        if (area <= 0) return null

        return SheetQuad(
            topLeft = topLeft,
            topRight = topRight,
            bottomRight = bottomRight,
            bottomLeft = bottomLeft,
            areaFraction = area / pixels.size,
        )
    }

    /**
     * Where the paper stops, probed outward from the aiming mark.
     *
     * Along each ray the sheet is bright and fairly even, and past its edge it
     * is darker and STAYS darker. That last part is what tells an edge from a
     * shadow: a shadow falls off and recovers, an edge does not. A hole or a
     * patch on the way out is dark too, which is why a single dark pixel does
     * not end the walk.
     */
    private fun sheetEdgePoints(
        pixels: IntArray,
        width: Int,
        height: Int,
        fit: TargetFit,
    ): List<Pair<Int, Int>> {
        fun at(x: Int, y: Int): Int? =
            if (x in 0 until width && y in 0 until height) pixels[y * width + x] else null

        // Paper, sampled just outside the mark, where the sheet certainly is.
        val ring = mutableListOf<Int>()
        for (index in 0 until 64) {
            val angle = 2.0 * Math.PI * index / 64
            at(
                (fit.cx + cos(angle) * fit.major * 1.3).toInt(),
                (fit.cy + sin(angle) * fit.major * 1.3).toInt(),
            )?.let(ring::add)
        }
        if (ring.isEmpty()) return emptyList()
        ring.sort()
        val edgeLevel = ring[ring.size / 2] * SHEET_EDGE_OF_PAPER

        val found = mutableListOf<Pair<Int, Int>>()
        for (index in 0 until SHEET_RAYS) {
            val angle = 2.0 * Math.PI * index / SHEET_RAYS
            val dx = cos(angle)
            val dy = sin(angle)
            var last: Pair<Int, Int>? = null
            var distance = fit.major * 1.3
            while (distance < fit.major * SHEET_REACH) {
                val x = (fit.cx + dx * distance).toInt()
                val y = (fit.cy + dy * distance).toInt()
                val here = at(x, y) ?: break
                if (here < edgeLevel) {
                    val ahead = (2..11).mapNotNull {
                        at(
                            (fit.cx + dx * (distance + it)).toInt(),
                            (fit.cy + dy * (distance + it)).toInt(),
                        )
                    }.sorted()
                    if (ahead.isNotEmpty() && ahead[ahead.size / 2] < edgeLevel) break
                }
                last = x to y
                distance += 2
            }
            last?.let(found::add)
        }
        if (found.size < 20) return found

        // A ray that got much further than the rest went through a gap in the
        // edge. The corners of a square legitimately reach 1.41 times the edge
        // distance, so the bar sits above that — below it, the corners are
        // trimmed off and the sheet comes out eight per cent too small.
        val radii = found.map { (x, y) -> hypot(x - fit.cx, y - fit.cy) }.sorted()
        val limit = SHEET_RAY_TRIM * radii[radii.size / 2]
        val kept = found.filter { (x, y) -> hypot(x - fit.cx, y - fit.cy) < limit }
        return if (kept.size >= 20) kept else found
    }

    /** Pixels of [mask] with at least one background neighbour. */
    @Suppress("unused")
    private fun boundaryOf(
        mask: BooleanArray,
        width: Int,
        height: Int,
    ): List<Pair<Int, Int>> {
        val points = mutableListOf<Pair<Int, Int>>()
        for (i in mask.indices) {
            if (!mask[i]) continue
            val x = i % width
            val y = i / width
            val edge = x == 0 || y == 0 || x == width - 1 || y == height - 1 ||
                !mask[i - 1] || !mask[i + 1] || !mask[i - width] || !mask[i + width]
            if (edge) points.add(x to y)
        }
        return points
    }

    /** Andrew's monotone chain. Counter-clockwise, no repeated endpoint. */
    internal fun convexHull(points: List<Pair<Int, Int>>): List<Pair<Int, Int>> {
        if (points.size < 3) return points
        val sorted = points.sortedWith(compareBy({ it.first }, { it.second }))

        fun cross(o: Pair<Int, Int>, a: Pair<Int, Int>, b: Pair<Int, Int>): Long {
            val x1 = (a.first - o.first).toLong()
            val y1 = (a.second - o.second).toLong()
            val x2 = (b.first - o.first).toLong()
            val y2 = (b.second - o.second).toLong()
            return x1 * y2 - y1 * x2
        }

        fun half(source: List<Pair<Int, Int>>): MutableList<Pair<Int, Int>> {
            val chain = mutableListOf<Pair<Int, Int>>()
            for (point in source) {
                while (chain.size >= 2 &&
                    cross(chain[chain.size - 2], chain[chain.size - 1], point) <= 0
                ) {
                    chain.removeAt(chain.size - 1)
                }
                chain.add(point)
            }
            chain.removeAt(chain.size - 1)
            return chain
        }

        return half(sorted) + half(sorted.asReversed())
    }

    /** Shoelace formula. */
    private fun polygonArea(points: List<Pair<Int, Int>>): Double {
        var sum = 0.0
        for (i in points.indices) {
            val (x1, y1) = points[i]
            val (x2, y2) = points[(i + 1) % points.size]
            sum += (x1.toDouble() * y2) - (x2.toDouble() * y1)
        }
        return abs(sum) / 2.0
    }

    // --- Step 2: the aiming mark ---

    internal fun findAimingMark(
        pixels: IntArray,
        width: Int,
        height: Int,
        sheet: BooleanArray?,
    ): TargetFit? {
        // Threshold over the sheet's own pixels only; including the dark
        // surroundings drags the split to the wrong place.
        val sample = if (sheet == null) pixels else {
            pixels.filterIndexed { i, _ -> sheet[i] }.toIntArray()
        }
        if (sample.isEmpty()) return null
        val level = otsu(sample)

        val dark = BooleanArray(pixels.size) { i ->
            pixels[i] <= level && (sheet == null || sheet[i])
        }

        val sheetWidth = sheet?.let { boundsWidth(it, width, height) }
            ?: min(width, height).toDouble()
        val maxMajor = MAX_MARK_OF_SHEET * sheetWidth / 2.0
        val minMajor = MIN_MARK_OF_SHEET * sheetWidth / 2.0

        var best: TargetFit? = null
        var bestScore = 0.0

        val labelling = label(dark, width, height)
        for (candidate in 1..labelling.count) {
            if (labelling.areas[candidate] < MIN_REGION_PX) continue
            // Ring 10 sits light inside the mark, so the region is a ring; its
            // moments only describe the mark once the hole is closed.
            val filled = fillHoles(labelling.maskOf(candidate), width, height)
            val fit = fitEllipse(filled, width, height) ?: continue

            if (fit.major !in minMajor..maxMajor) continue
            if (fit.circularity < 0.35) continue

            val filledArea = filled.count { it }.toDouble()
            val ellipseArea = Math.PI * fit.major * fit.minor
            if (ellipseArea <= 0.0) continue
            val fill = filledArea / ellipseArea
            if (fill < MIN_FILL) continue

            val score = fill * filledArea
            if (score > bestScore) {
                bestScore = score
                best = fit
            }
        }
        return best
    }

    /**
     * Correct the scale using the target's own printed rings.
     *
     * The aiming mark is one measurement, taken from an edge that is shot to
     * pieces after a few series — its centroid drifts with every hole in the
     * rim. The printed rings are ten more measurements, spread across the whole
     * sheet, where local damage averages out.
     *
     * Measured over 142 club photographs this cut the spread from 4.1 mm to
     * 2.7 mm and took the systematic error from +0.6% to +0.1%. It matters
     * beyond the picture looking right: every automatically detected hit will
     * get its ring from this geometry, and the training labels for that detector
     * come from these same coordinates. Sloppy here is sloppy everywhere after.
     *
     * @param rectified grayscale square produced by rectifying at [frameToScoring]
     * @return factor to multiply the fitted radii by, or null if no ring line
     *   could be read — an overexposed or very blurred photo.
     */
    fun refineScale(
        rectified: IntArray,
        size: Int,
        geometry: TargetGeometry,
        frameToScoring: Double = TargetGeometry.FRAME_TO_SCORING,
    ): Double? {
        require(rectified.size == size * size) { "expected a square image" }
        val scoringPx = size / (2.0 * frameToScoring)
        val centre = size / 2.0

        val errors = mutableListOf<Double>()
        for (ring in REFINE_RINGS) {
            val expected = scoringPx * geometry.ringFraction(ring)
            if (expected < 20 || expected > scoringPx) continue

            // Median brightness around each candidate radius. A median, not a
            // mean: shot holes and patches are dark too, and a mean would let a
            // handful of them drag the whole ring.
            var darkestRadius = -1.0
            var darkest = Double.MAX_VALUE
            var radius = expected - REFINE_SEARCH_PX
            while (radius <= expected + REFINE_SEARCH_PX) {
                val samples = ArrayList<Int>(REFINE_ANGLES)
                for (i in 0 until REFINE_ANGLES) {
                    val angle = 2.0 * Math.PI * i / REFINE_ANGLES
                    val x = (centre + cos(angle) * radius).toInt()
                    val y = (centre + sin(angle) * radius).toInt()
                    if (x in 0 until size && y in 0 until size) samples.add(rectified[y * size + x])
                }
                if (samples.size >= REFINE_ANGLES / 2) {
                    samples.sort()
                    val median = samples[samples.size / 2].toDouble()
                    if (median < darkest) {
                        darkest = median
                        darkestRadius = radius
                    }
                }
                radius += 1.0
            }
            if (darkestRadius > 0) errors.add((darkestRadius - expected) / expected)
        }

        if (errors.size < 2) return null
        errors.sort()
        val median = errors[errors.size / 2]
        // A correction beyond this is not a refinement, it is a different
        // target — better to keep the mark's own measurement than to trust it.
        if (abs(median) > MAX_REFINE) return null
        return 1.0 + median
    }

    /**
     * Rings used for refinement: outside the black, where the printed line is
     * dark on light paper. Inside the mark the contrast inverts and the same
     * search would find nothing.
     */
    private val REFINE_RINGS = intArrayOf(2, 3, 4, 5)
    private const val REFINE_SEARCH_PX = 14.0
    private const val REFINE_ANGLES = 180
    private const val MAX_REFINE = 0.08

    // --- Ellipse from image moments ---

    /**
     * Fit an ellipse to a filled region using its second-order moments.
     *
     * Not a least-squares fit to the boundary: for a solid region the moments
     * give the same answer in one pass, with no eigen-solver and no iteration.
     * For a filled ellipse `mu20/m00 == a²/4`, which is where the factor of two
     * below comes from.
     */
    internal fun fitEllipse(mask: BooleanArray, width: Int, height: Int): TargetFit? {
        var m00 = 0.0
        var m10 = 0.0
        var m01 = 0.0
        for (y in 0 until height) {
            val row = y * width
            for (x in 0 until width) {
                if (!mask[row + x]) continue
                m00 += 1.0
                m10 += x
                m01 += y
            }
        }
        if (m00 < 5) return null

        val cx = m10 / m00
        val cy = m01 / m00

        var mu20 = 0.0
        var mu02 = 0.0
        var mu11 = 0.0
        for (y in 0 until height) {
            val row = y * width
            val dy = y - cy
            for (x in 0 until width) {
                if (!mask[row + x]) continue
                val dx = x - cx
                mu20 += dx * dx
                mu02 += dy * dy
                mu11 += dx * dy
            }
        }
        mu20 /= m00
        mu02 /= m00
        mu11 /= m00

        // Eigenvalues of the 2x2 covariance matrix.
        val common = sqrt((mu20 - mu02) * (mu20 - mu02) + 4.0 * mu11 * mu11)
        val lambda1 = (mu20 + mu02 + common) / 2.0
        val lambda2 = (mu20 + mu02 - common) / 2.0
        if (lambda1 <= 0.0 || lambda2 <= 0.0) return null

        val major = 2.0 * sqrt(lambda1)
        val minor = 2.0 * sqrt(lambda2)
        // Angle of the major axis. atan2 of the leading eigenvector.
        val angle = Math.toDegrees(0.5 * atan2(2.0 * mu11, mu20 - mu02))

        return TargetFit(cx, cy, major, minor, angle, minor / major)
    }

    // --- Thresholding ---

    /**
     * Otsu's threshold over 8-bit values.
     *
     * Split as OpenCV does it — `value > threshold` is the bright side — so this
     * and the Python reference classify the same pixels. Using `>=` put the
     * threshold value itself on the wrong side of the line.
     */
    internal fun otsu(values: IntArray): Int {
        val histogram = IntArray(256)
        for (v in values) histogram[v.coerceIn(0, 255)]++
        val total = values.size.toDouble()

        var sum = 0.0
        for (i in 0..255) sum += i * histogram[i]

        var sumBackground = 0.0
        var weightBackground = 0.0
        var bestVariance = -1.0
        var threshold = 0

        for (t in 0..255) {
            weightBackground += histogram[t]
            if (weightBackground == 0.0) continue
            val weightForeground = total - weightBackground
            if (weightForeground <= 0.0) break

            sumBackground += t * histogram[t]
            val meanBackground = sumBackground / weightBackground
            val meanForeground = (sum - sumBackground) / weightForeground
            val diff = meanBackground - meanForeground
            val variance = weightBackground * weightForeground * diff * diff

            if (variance > bestVariance) {
                bestVariance = variance
                threshold = t
            }
        }
        return threshold
    }

    // --- Connected components ---

    /**
     * Connected-component labelling, four-connected.
     *
     * Returns a label per pixel (0 = background) and the area of each label,
     * rather than a bitmask per region: a photo thresholds into thousands of
     * specks, and one full-frame BooleanArray each would be gigabytes. Masks are
     * materialised only for the few candidates worth measuring.
     */
    internal class Labelling(val labels: IntArray, val areas: IntArray) {
        val count: Int get() = areas.size - 1

        /** The mask of one label, for the handful that get measured. */
        fun maskOf(label: Int): BooleanArray = BooleanArray(labels.size) { labels[it] == label }

        fun largest(): Int? =
            (1..count).maxByOrNull { areas[it] }?.takeIf { areas.isNotEmpty() && count > 0 }
    }

    /**
     * Iterative flood fill with an explicit stack — recursion overflows on a
     * full-frame region long before it finishes.
     *
     * @param diagonal join regions that meet only at a corner. Off for the sheet
     *   and the mark, where it would bridge two dark surfaces that happen to
     *   touch; on for [HitDetector], where the fragments of one torn hole
     *   frequently do meet at a corner and are one hole.
     */
    internal fun label(
        mask: BooleanArray,
        width: Int,
        height: Int,
        diagonal: Boolean = false,
    ): Labelling {
        val labels = IntArray(mask.size)
        val areas = mutableListOf(0) // index 0 is background
        val stack = IntArray(mask.size)

        for (seed in mask.indices) {
            if (!mask[seed] || labels[seed] != 0) continue

            val current = areas.size
            var area = 0
            var top = 0
            stack[top++] = seed
            labels[seed] = current

            while (top > 0) {
                val index = stack[--top]
                area++
                val x = index % width
                val y = index / width

                if (x > 0) {
                    val n = index - 1
                    if (mask[n] && labels[n] == 0) { labels[n] = current; stack[top++] = n }
                }
                if (x < width - 1) {
                    val n = index + 1
                    if (mask[n] && labels[n] == 0) { labels[n] = current; stack[top++] = n }
                }
                if (y > 0) {
                    val n = index - width
                    if (mask[n] && labels[n] == 0) { labels[n] = current; stack[top++] = n }
                }
                if (y < height - 1) {
                    val n = index + width
                    if (mask[n] && labels[n] == 0) { labels[n] = current; stack[top++] = n }
                }
                if (diagonal) {
                    for (dy in -1..1 step 2) {
                        val ny = y + dy
                        if (ny !in 0 until height) continue
                        for (dx in -1..1 step 2) {
                            val nx = x + dx
                            if (nx !in 0 until width) continue
                            val n = ny * width + nx
                            if (mask[n] && labels[n] == 0) {
                                labels[n] = current
                                stack[top++] = n
                            }
                        }
                    }
                }
            }
            areas.add(area)
        }
        return Labelling(labels, areas.toIntArray())
    }

    /**
     * Close interior holes: flood the background inward from the border, and
     * whatever background was never reached was enclosed.
     */
    internal fun fillHoles(mask: BooleanArray, width: Int, height: Int): BooleanArray {
        val outside = BooleanArray(mask.size)
        val stack = IntArray(mask.size)
        var top = 0

        fun seed(index: Int) {
            if (!mask[index] && !outside[index]) {
                outside[index] = true
                stack[top++] = index
            }
        }
        for (x in 0 until width) {
            seed(x)
            seed((height - 1) * width + x)
        }
        for (y in 0 until height) {
            seed(y * width)
            seed(y * width + width - 1)
        }

        while (top > 0) {
            val index = stack[--top]
            val x = index % width
            val y = index / width
            if (x > 0) seed(index - 1)
            if (x < width - 1) seed(index + 1)
            if (y > 0) seed(index - width)
            if (y < height - 1) seed(index + width)
        }
        return BooleanArray(mask.size) { mask[it] || !outside[it] }
    }

    private fun boundsWidth(mask: BooleanArray, width: Int, height: Int): Double {
        var minX = width
        var maxX = -1
        for (y in 0 until height) {
            val row = y * width
            for (x in 0 until width) {
                if (!mask[row + x]) continue
                if (x < minX) minX = x
                if (x > maxX) maxX = x
            }
        }
        return if (maxX < minX) width.toDouble() else (maxX - minX).toDouble()
    }

}

/**
 * The sheet as seen in the frame, for the viewfinder outline.
 *
 * @param areaFraction how much of the frame it covers — the app asks the user to
 *   come closer when the sheet is too small to measure well.
 */
data class SheetQuad(
    val topLeft: Pair<Int, Int>,
    val topRight: Pair<Int, Int>,
    val bottomRight: Pair<Int, Int>,
    val bottomLeft: Pair<Int, Int>,
    val areaFraction: Double,
) {
    /**
     * Big enough in frame that the aiming mark has pixels to spare.
     *
     * Below this the mark is a few dozen pixels across and the scale it yields
     * is guesswork — better to ask for a step closer than to measure badly.
     */
    val closeEnough: Boolean get() = areaFraction >= MIN_AREA

    companion object {
        const val MIN_AREA = 0.25
    }
}

/**
 * Where the aiming mark is, in the pixels of the image that was analysed.
 *
 * Mirrors `TargetFit` in `ml/scripts/rectify.py`.
 */
data class TargetFit(
    val cx: Double,
    val cy: Double,
    /** Semi-major axis in pixels. */
    val major: Double,
    /** Semi-minor axis in pixels. */
    val minor: Double,
    /** Rotation of the MAJOR axis, degrees. */
    val angle: Double,
    /** minor/major — 1.0 is dead-on, lower is more oblique. */
    val circularity: Double,
) {
    /** Too oblique for the affine rectification to be trusted. */
    val oblique: Boolean get() = circularity < TargetLocator.OBLIQUE_WARN

    /**
     * Image point → target coordinates, normalised to the ring 1 radius.
     *
     * Undoes the ellipse back to a circle: rotate the major axis onto x, stretch
     * the short axis back, rotate back. That is enough for the ring lookup,
     * which only cares about radial distance — and over 142 real photos the
     * worst was 0.96 circular, so the approximation has plenty of headroom.
     *
     * @param blackRatio aiming mark diameter over ring 1 diameter. Scheibe Nr. 5
     *   is 200/500; it differs per target, so it is not a constant.
     */
    fun toTarget(x: Double, y: Double, blackRatio: Double): Pair<Double, Double> {
        val theta = Math.toRadians(angle)
        val cos = cos(theta)
        val sin = sin(theta)

        val dx = x - cx
        val dy = y - cy
        // Into the ellipse's own frame.
        val u = dx * cos + dy * sin
        val v = -dx * sin + dy * cos
        // Un-squash the short axis, then scale so the mark's radius is
        // `blackRatio` of the scoring radius.
        val scale = blackRatio / major
        val nx = u * scale
        val ny = v * (major / minor) * scale
        // Back out of the ellipse frame.
        return (nx * cos - ny * sin) to (nx * sin + ny * cos)
    }

    /** Distance from the target centre, normalised to the ring 1 radius. */
    fun normalisedDistance(x: Double, y: Double, blackRatio: Double): Double {
        val (nx, ny) = toTarget(x, y, blackRatio)
        return hypot(nx, ny)
    }

    /**
     * Target coordinates → the pixel they came from. The inverse of [toTarget].
     *
     * Rectifying an image works backwards: for every pixel of the output, ask
     * which pixel of the photo belongs there. Going forwards would leave holes
     * wherever the source is stretched.
     */
    fun toImage(nx: Double, ny: Double, blackRatio: Double): Pair<Double, Double> {
        val theta = Math.toRadians(angle)
        val cos = cos(theta)
        val sin = sin(theta)

        // Into the ellipse's frame, re-squash the short axis, scale back to px.
        val u = nx * cos + ny * sin
        val v = -nx * sin + ny * cos
        val scale = major / blackRatio
        val eu = u * scale
        val ev = v * (minor / major) * scale

        return (cx + eu * cos - ev * sin) to (cy + eu * sin + ev * cos)
    }

    /**
     * The square that rectifying will actually cut out, in image pixels.
     *
     * This is what the viewfinder draws. It is derived from the aiming mark and
     * nothing else, exactly like the crop itself — so the outline on screen and
     * the picture the detector gets are the same region by construction.
     *
     * It replaced an outline traced from the sheet's own edge, which failed on
     * the range this was built for. Those rays walk outward until brightness
     * falls below a fraction of the paper level, and a target hung on a BRIGHT
     * backstop has no such fall: yellow sheet and lilac backstop are nearly
     * identical in grey, and the frames are converted to grey before analysis.
     * The rays ran straight through the sheet and stopped at the outer edge of
     * the backstop panel — a green outline around a metre of wall, photographed
     * on 2026-08-07. Colour would separate the two, but the mark is standardised
     * and already measured, so there is nothing to search for.
     *
     * @param blackRatio aiming mark diameter over ring 1 diameter — per target.
     */
    fun cropOutline(
        width: Int,
        height: Int,
        blackRatio: Double,
        frameToScoring: Double = TargetGeometry.FRAME_TO_SCORING,
    ): SheetQuad {
        val edge = frameToScoring
        val corners = listOf(
            -edge to -edge, edge to -edge, edge to edge, -edge to edge,
        ).map { (nx, ny) ->
            val (x, y) = toImage(nx, ny, blackRatio)
            x.roundToInt() to y.roundToInt()
        }

        // Shoelace over the four corners: how much of the frame the crop covers,
        // which is what decides "close enough to shoot".
        var twiceArea = 0.0
        for (i in corners.indices) {
            val (x1, y1) = corners[i]
            val (x2, y2) = corners[(i + 1) % corners.size]
            twiceArea += x1.toDouble() * y2 - x2.toDouble() * y1
        }
        val area = abs(twiceArea) / 2.0

        return SheetQuad(
            topLeft = corners[0],
            topRight = corners[1],
            bottomRight = corners[2],
            bottomLeft = corners[3],
            areaFraction = (area / (width.toDouble() * height)).coerceIn(0.0, 1.0),
        )
    }
}
