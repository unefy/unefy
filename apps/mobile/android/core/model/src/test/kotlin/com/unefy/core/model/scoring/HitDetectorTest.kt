package com.unefy.core.model.scoring

import java.awt.image.BufferedImage
import java.io.File
import javax.imageio.ImageIO
import kotlin.math.abs
import kotlin.math.hypot
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Cross-checks [HitDetector] against `ml/scripts/detect_hits.py` on real crops.
 *
 * The fixtures under `resources/hits/` are club photographs put through the
 * Python rectifier, and `expected.json` holds the holes the Python detector
 * found in those exact files — written by `ml/scripts/export_fixtures.py`, which
 * also records how many holes a human confirmed in each. Two implementations of
 * the same algorithm drifting apart is the failure this prevents, the same
 * arrangement [TargetLocatorTest] has for the geometry.
 *
 * Real photographs on purpose. A synthetic target with black discs on it would
 * pass whatever the thresholds were, and would contain none of what the job
 * actually consists of: patches that outnumber the holes, seams between patches
 * that are darker than anything else on the sheet, and holes in paper that are
 * grey rather than black because the backstop shows through them.
 */
class HitDetectorTest {

    private data class Fixture(
        val image: String,
        val why: String,
        val hits: List<Pair<Double, Double>>,
        val checked: Int,
    )

    /** Scheibe Nr. 5 — what every fixture was photographed on. */
    private val geometry = TargetGeometrySeed.DEFAULT

    /**
     * How far a hole may sit from where Python put it and still be the same
     * hole, in millimetres.
     *
     * Not zero, and it cannot be: the two implementations round differently in
     * a handful of places — the median of an even number of pixels, the integer
     * arithmetic in the blur — and a pixel is 0.39 mm. A tenth of that is well
     * inside the width of a shot hole and nowhere near a ring boundary, which is
     * what the number has to be good enough for.
     */
    private val toleranceMm = 1.0

    private fun fixtures(): List<Fixture> {
        val json = resource("hits/expected.json").readText()
        // A hand-rolled reader, as in TargetLocatorTest: core:model is pure
        // Kotlin with no serialization dependency, and one test fixture is not
        // reason enough to add one.
        return Regex("\\{\\s*\"image\"[\\s\\S]*?\"checked\":\\s*\\d+\\s*}")
            .findAll(json)
            .map { block ->
                val image = Regex("\"image\":\\s*\"([^\"]+)\"")
                    .find(block.value)!!.groupValues[1]
                val why = Regex("\"why\":\\s*\"([^\"]*)\"")
                    .find(block.value)!!.groupValues[1]
                val checked = Regex("\"checked\":\\s*(\\d+)")
                    .find(block.value)!!.groupValues[1].toInt()
                val hits = Regex("\"x_mm\":\\s*(-?[\\d.]+),\\s*\"y_mm\":\\s*(-?[\\d.]+)")
                    .findAll(block.value)
                    .map { it.groupValues[1].toDouble() to it.groupValues[2].toDouble() }
                    .toList()
                Fixture(image, why, hits, checked)
            }
            .toList()
    }

    private fun resource(path: String): File =
        File(checkNotNull(javaClass.classLoader.getResource(path)) { "missing $path" }.toURI())

    /**
     * 8-bit grayscale, row-major — the shape the detector expects.
     *
     * Read out of the raster and not through `getRGB`: on a grayscale image
     * `getRGB` converts the stored value from linear grey to sRGB, which lifts
     * a hole from 68 to 141 and quietly puts every threshold in a different
     * place than the Python reference measured.
     */
    private fun grayscale(file: File): Pair<IntArray, Int> {
        val image = ImageIO.read(file)
        assertEquals("${file.name}: fixtures are square crops", image.width, image.height)
        val pixels = IntArray(image.width * image.height)
        val grey = image.type == BufferedImage.TYPE_BYTE_GRAY
        val raster = image.raster
        for (y in 0 until image.height) {
            for (x in 0 until image.width) {
                pixels[y * image.width + x] = if (grey) {
                    raster.getSample(x, y, 0)
                } else {
                    val rgb = image.getRGB(x, y)
                    val r = (rgb shr 16) and 0xFF
                    val g = (rgb shr 8) and 0xFF
                    val b = rgb and 0xFF
                    // The luma weights OpenCV's COLOR_BGR2GRAY uses, so both
                    // implementations threshold identical numbers.
                    (0.299 * r + 0.587 * g + 0.114 * b).toInt()
                }
            }
        }
        return pixels to image.width
    }

    private fun detect(fixture: Fixture): List<Pair<Double, Double>> {
        val (pixels, size) = grayscale(resource("hits/${fixture.image}"))
        return HitDetector.detect(pixels, size, geometry).map { hit ->
            hit.x * geometry.scoringRadiusMm to hit.y * geometry.scoringRadiusMm
        }
    }

    @Test
    fun `finds the same holes as the Python reference`() {
        val cases = fixtures()
        assertTrue("no fixtures found", cases.isNotEmpty())

        for (case in cases) {
            val found = detect(case)
            val unmatched = case.hits.filter { (x, y) ->
                found.none { hypot(it.first - x, it.second - y) <= toleranceMm }
            }
            assertTrue(
                "${case.image} (${case.why}): Python found ${case.hits.size} holes, " +
                    "this found ${found.size}; missing $unmatched",
                unmatched.isEmpty(),
            )
            assertEquals(
                "${case.image}: reported a different number of holes than Python",
                case.hits.size,
                found.size,
            )
        }
    }

    @Test
    fun `positions agree to well under a ring`() {
        for (case in fixtures()) {
            val found = detect(case)
            for ((x, y) in case.hits) {
                val nearest = found.minByOrNull { hypot(it.first - x, it.second - y) } ?: continue
                val off = hypot(nearest.first - x, nearest.second - y)
                assertTrue(
                    "${case.image}: hole at ($x, $y) mm came out ${"%.2f".format(off)} mm away",
                    off <= toleranceMm,
                )
            }
        }
    }

    @Test
    fun `a freshly patched target reports nothing`() {
        // The case that matters most in the club: after every series the holes
        // are patched, so most sheets a phone ever sees have forty patches and
        // no fresh hole. Anything reported here would be reported on all of them
        // — and the seams between overlapping patches are the darkest thing on
        // the sheet after the holes themselves.
        val patched = fixtures().first { it.checked == 0 }
        assertEquals(
            "${patched.image} (${patched.why}) must report no holes",
            0,
            detect(patched).size,
        )
    }

    @Test
    fun `every hole a human confirmed is reported`() {
        // The Python side is scored against hand-checked holes by
        // ml/scripts/score_hits.py; this only repeats the count, so that a
        // Kotlin change which agrees with a broken Python still fails.
        for (case in fixtures()) {
            assertEquals(
                "${case.image}: ${case.checked} holes were confirmed by hand",
                case.checked,
                detect(case).size,
            )
        }
    }

    @Test
    fun `the distance transform is exact`() {
        // Everything the splitter does rests on this, and an approximation was
        // the tempting alternative. A 5x5 block of foreground inside a ring of
        // background, so the true distance is known for every pixel: the corners
        // of the block are 1 away from the outside, its middle 3.
        val side = 7
        val inside = BooleanArray(side * side) { index ->
            val x = index % side
            val y = index / side
            x in 1..5 && y in 1..5
        }
        val distance = HitDetector.distanceTransform(inside, side, side)

        for (y in 1..5) {
            for (x in 1..5) {
                val expected = minOf(x, y, side - 1 - x, side - 1 - y).toDouble()
                assertEquals(
                    "distance at ($x, $y)",
                    expected,
                    distance[y * side + x],
                    1e-9,
                )
            }
        }
        assertEquals("background is zero", 0.0, distance[0], 1e-9)
    }

    @Test
    fun `the traced perimeter matches the shape`() {
        // A 10x10 square: 36 boundary pixels, traced as 36 orthogonal steps.
        val size = 20
        val pixels = mutableListOf<Int>()
        for (y in 5 until 15) {
            for (x in 5 until 15) pixels.add(y * size + x)
        }
        val perimeter = HitDetector.tracePerimeter(pixels.toIntArray(), size)
        assertEquals("square of side 10", 36.0, perimeter, 0.001)

        // A disc: the traced length must land near the true circumference, or
        // the roundness gate would be measuring the staircase instead.
        val radius = 12
        val disc = mutableListOf<Int>()
        val field = 40
        for (y in 0 until field) {
            for (x in 0 until field) {
                if (hypot(x - 20.0, y - 20.0) <= radius) disc.add(y * field + x)
            }
        }
        val circumference = 2 * Math.PI * radius
        val traced = HitDetector.tracePerimeter(disc.toIntArray(), field)
        assertTrue(
            "disc of radius $radius traced as $traced, circumference is $circumference",
            abs(traced - circumference) / circumference < 0.12,
        )
    }
}
