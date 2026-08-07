package com.unefy.core.model.scoring

import java.io.File
import javax.imageio.ImageIO
import kotlin.math.abs
import kotlin.math.hypot
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Cross-checks [TargetLocator] against `ml/scripts/rectify.py` on real photos.
 *
 * The fixtures under `resources/targets/` are club photographs, downscaled;
 * `expected.json` holds what the Python reference measured on those exact
 * images. Two implementations of the same geometry drifting apart is the failure
 * this prevents — the same arrangement as [ScoringEngineTest] and the Python
 * scoring tests.
 *
 * They are real photos on purpose. Synthetic circles would have passed happily
 * while missing both of the faults real ones exposed: the grey backstop being
 * mistaken for the aiming mark, and a "mark" wider than the whole sheet being
 * accepted without complaint (ml/NOTES-real-targets.md).
 */
class TargetLocatorTest {

    private data class Expected(
        val image: String,
        val width: Int,
        val height: Int,
        val cx: Double,
        val cy: Double,
        val major: Double,
        val minor: Double,
        val circularity: Double,
    )

    private fun fixtures(): List<Expected> {
        val json = resource("targets/expected.json").readText()
        // A hand-rolled reader: core:model is pure Kotlin with no serialization
        // dependency, and adding one for a test fixture is not worth it.
        return Regex("\\{[^}]*}").findAll(json).map { match ->
            val fields = Regex("\"(\\w+)\":\\s*(\"[^\"]*\"|[-\\d.]+)")
                .findAll(match.value)
                .associate { it.groupValues[1] to it.groupValues[2].trim('"') }
            Expected(
                image = fields.getValue("image"),
                width = fields.getValue("width").toInt(),
                height = fields.getValue("height").toInt(),
                cx = fields.getValue("cx").toDouble(),
                cy = fields.getValue("cy").toDouble(),
                major = fields.getValue("major").toDouble(),
                minor = fields.getValue("minor").toDouble(),
                circularity = fields.getValue("circularity").toDouble(),
            )
        }.toList()
    }

    private fun resource(path: String): File =
        File(checkNotNull(javaClass.classLoader.getResource(path)) { "missing $path" }.toURI())

    /** 8-bit grayscale, row-major — the shape [TargetLocator.locate] expects. */
    private fun grayscale(file: File): Triple<IntArray, Int, Int> {
        val image = ImageIO.read(file)
        val width = image.width
        val height = image.height
        val pixels = IntArray(width * height)
        for (y in 0 until height) {
            for (x in 0 until width) {
                val rgb = image.getRGB(x, y)
                val r = (rgb shr 16) and 0xFF
                val g = (rgb shr 8) and 0xFF
                val b = rgb and 0xFF
                // Same luma weights OpenCV's COLOR_BGR2GRAY uses, so the two
                // implementations threshold identical numbers.
                pixels[y * width + x] = (0.299 * r + 0.587 * g + 0.114 * b).toInt()
            }
        }
        return Triple(pixels, width, height)
    }

    @Test
    fun `every fixture is located`() {
        val cases = fixtures()
        assertTrue("no fixtures found", cases.isNotEmpty())

        for (case in cases) {
            val (pixels, width, height) = grayscale(resource("targets/${case.image}"))
            assertNotNull("${case.image}: no target found", TargetLocator.locate(pixels, width, height))
        }
    }

    @Test
    fun `centre agrees with the python reference`() {
        for (case in fixtures()) {
            val (pixels, width, height) = grayscale(resource("targets/${case.image}"))
            val fit = checkNotNull(TargetLocator.locate(pixels, width, height))

            // 2% of the image's long edge. The two use different ellipse fits —
            // moments here, least squares on the contour in OpenCV — so they are
            // not expected to agree to the pixel, only to agree on the target.
            val tolerance = 0.02 * maxOf(width, height)
            val error = hypot(fit.cx - case.cx, fit.cy - case.cy)
            assertTrue(
                "${case.image}: centre off by ${"%.1f".format(error)}px " +
                    "(kotlin ${fit.cx.toInt()},${fit.cy.toInt()} vs " +
                    "python ${case.cx.toInt()},${case.cy.toInt()}), tolerance ${tolerance.toInt()}",
                error <= tolerance,
            )
        }
    }

    @Test
    fun `scale agrees with the python reference`() {
        // The scale is what turns pixels into millimetres, so an error here is an
        // error in every ring value that follows.
        for (case in fixtures()) {
            val (pixels, width, height) = grayscale(resource("targets/${case.image}"))
            val fit = checkNotNull(TargetLocator.locate(pixels, width, height))

            val error = abs(fit.major - case.major) / case.major
            assertTrue(
                "${case.image}: radius off by ${"%.0f".format(error * 100)}% " +
                    "(kotlin ${fit.major.toInt()} vs python ${case.major.toInt()})",
                error <= 0.10,
            )
        }
    }

    @Test
    fun `obliqueness agrees with the python reference`() {
        for (case in fixtures()) {
            val (pixels, width, height) = grayscale(resource("targets/${case.image}"))
            val fit = checkNotNull(TargetLocator.locate(pixels, width, height))

            assertEquals(
                "${case.image}: circularity",
                case.circularity,
                fit.circularity,
                0.08,
            )
        }
    }

    @Test
    fun `the club's photos are square-on enough for the affine rectification`() {
        // Measured over all 142: worst 0.96. If a fixture ever drops below the
        // warning threshold, the full homography stops being optional.
        for (case in fixtures()) {
            val (pixels, width, height) = grayscale(resource("targets/${case.image}"))
            val fit = checkNotNull(TargetLocator.locate(pixels, width, height))
            assertTrue(
                "${case.image}: unexpectedly oblique at ${"%.2f".format(fit.circularity)}",
                !fit.oblique,
            )
        }
    }

    // --- Coordinate mapping ---

    @Test
    fun `the mark's own edge maps to the black ratio`() {
        // A point on the aiming mark's boundary is, by definition, at
        // blackRatio of the scoring radius. This is the mapping's anchor.
        val fit = TargetFit(cx = 100.0, cy = 100.0, major = 50.0, minor = 50.0, angle = 0.0, circularity = 1.0)
        val ratio = 200.0 / 500.0

        assertEquals(ratio, fit.normalisedDistance(150.0, 100.0, ratio), 1e-9)
        assertEquals(ratio, fit.normalisedDistance(100.0, 150.0, ratio), 1e-9)
        assertEquals(0.0, fit.normalisedDistance(100.0, 100.0, ratio), 1e-9)
    }

    @Test
    fun `an oblique fit still maps to a circle`() {
        // The whole point of rectifying: a squashed target must produce the same
        // normalised distance in every direction, or ring values would depend on
        // which way the camera was held.
        val squashed = TargetFit(
            cx = 100.0, cy = 100.0, major = 50.0, minor = 25.0, angle = 0.0, circularity = 0.5,
        )
        val ratio = 0.4

        // Along the major axis, and along the (squashed) minor axis.
        assertEquals(ratio, squashed.normalisedDistance(150.0, 100.0, ratio), 1e-9)
        assertEquals(ratio, squashed.normalisedDistance(100.0, 125.0, ratio), 1e-9)
    }

    @Test
    fun `a rotated oblique fit still maps to a circle`() {
        val rotated = TargetFit(
            cx = 0.0, cy = 0.0, major = 50.0, minor = 25.0, angle = 30.0, circularity = 0.5,
        )
        val ratio = 0.4
        val theta = Math.toRadians(30.0)

        // A point on the ellipse boundary along the major axis at 30°.
        val x = 50.0 * kotlin.math.cos(theta)
        val y = 50.0 * kotlin.math.sin(theta)
        assertEquals(ratio, rotated.normalisedDistance(x, y, ratio), 1e-9)
    }



    @Test
    fun `toImage is the inverse of toTarget`() {
        // Rectifying an image samples backwards — for every output pixel, which
        // source pixel belongs there — so the two mappings have to agree
        // exactly, including for an oblique, rotated fit.
        val fit = TargetFit(
            cx = 320.0, cy = 240.0, major = 80.0, minor = 55.0, angle = 23.0, circularity = 0.69,
        )
        val ratio = 0.4

        for (point in listOf(
            0.0 to 0.0,
            0.5 to 0.0,
            0.0 to -0.7,
            -0.35 to 0.62,
            1.0 to 1.0,
        )) {
            val (px, py) = fit.toImage(point.first, point.second, ratio)
            val (bx, by) = fit.toTarget(px, py, ratio)
            assertEquals("x round-trip for $point", point.first, bx, 1e-9)
            assertEquals("y round-trip for $point", point.second, by, 1e-9)
        }
    }

    // --- The two safeguards real photographs forced ---
    //
    // Both are covered here rather than by the photo fixtures: those are
    // downscaled to 512px for the repository, and at that size neither fault
    // reproduces. Removing either safeguard left every fixture green, which
    // makes these scenes the only thing standing behind them.

    /**
     * A sheet on a grey backstop, in the proportions of a real range photo.
     *
     * The backstop is mid-grey — darker than paper, far brighter than the black
     * mark. That is exactly the arrangement that fooled the first version: one
     * threshold pass puts backstop and paper on the same side, and the backstop
     * then becomes the biggest dark region inside the "sheet".
     */
    private fun sheetOnBackstop(
        size: Int = 400,
        sheetHalf: Int = 120,
        markRadius: Int = 42,
        /**
         * Grey of the backstop behind the sheet. The default is a clearly darker
         * one; pass a value near the paper's 235 for the case the club's range
         * actually presents — a lilac backstop that photographs almost exactly
         * as bright as the yellow sheet, where no brightness rule can find the
         * paper's edge.
         */
        backstop: Int = 140,
    ): Triple<IntArray, Int, Int> {
        val pixels = IntArray(size * size) { 25 }      // dark surroundings
        val backstopHalf = 170
        val centre = size / 2

        for (y in 0 until size) {
            for (x in 0 until size) {
                val dx = abs(x - centre)
                val dy = abs(y - centre)
                val value = when {
                    dx <= markRadius && dy <= markRadius &&
                        hypot((x - centre).toDouble(), (y - centre).toDouble()) <= markRadius -> 20
                    dx <= sheetHalf && dy <= sheetHalf -> 235   // paper
                    dx <= backstopHalf && dy <= backstopHalf -> backstop
                    else -> 25
                }
                pixels[y * size + x] = value
            }
        }
        return Triple(pixels, size, size)
    }

    @Test
    fun `the grey backstop is not mistaken for the aiming mark`() {
        val (pixels, width, height) = sheetOnBackstop(markRadius = 42)
        val fit = checkNotNull(TargetLocator.locate(pixels, width, height)) {
            "no target found at all"
        }
        // The mark is 42px; the backstop would come out around 170.
        assertEquals("radius — 170 would mean the backstop won", 42.0, fit.major, 6.0)
    }

    @Test
    fun `the sheet mask excludes the backstop`() {
        val (pixels, width, height) = sheetOnBackstop()
        val sheet = checkNotNull(TargetLocator.findSheet(pixels, width, height))
        // Paper is 240x240 of a 400x400 frame; including the backstop would be
        // 340x340, nearly twice the area.
        val area = sheet.count { it }
        assertTrue("sheet covers $area px, expected roughly 240x240", area in 45_000..75_000)
    }

    @Test
    fun `a mark wider than the sheet is rejected`() {
        // The concrete failure from the field: a fit 1.56x the sheet's own width
        // was accepted, and the resulting scale was wrong by a factor of four.
        val size = 400
        val pixels = IntArray(size * size) { 25 }
        val centre = size / 2
        for (y in 0 until size) {
            for (x in 0 until size) {
                val dx = abs(x - centre)
                val dy = abs(y - centre)
                // A small sheet with a huge dark blob spilling well past it.
                if (dx <= 60 && dy <= 60) pixels[y * size + x] = 235
                if (hypot((x - centre).toDouble(), (y - centre).toDouble()) <= 150) {
                    if (!(dx <= 60 && dy <= 60)) pixels[y * size + x] = 20
                }
            }
        }
        val sheet = TargetLocator.findSheet(pixels, size, size)
        val fit = TargetLocator.findAimingMark(pixels, size, size, sheet)
        if (fit != null) {
            val sheetWidth = 120.0
            assertTrue(
                "accepted a mark of ${fit.major * 2} across a sheet of $sheetWidth",
                fit.major * 2 <= TargetLocator.MAX_MARK_OF_SHEET * sheetWidth * 1.2,
            )
        }
    }


    // --- Strict mode: the live viewfinder ---
    //
    // A preview frame is whatever the camera is pointed at, and the lenient
    // search finds "a target" in almost anything dark. That is fine for a photo
    // the user deliberately framed; in a preview it fired the shutter at
    // doorways and shadows.

    @Test
    fun `strict mode rejects a frame with no sheet in it`() {
        // A dark blob on a dark background: no bright paper anywhere.
        val size = 300
        val pixels = IntArray(size * size) { 60 }
        for (y in 100 until 200) {
            for (x in 100 until 200) {
                if (hypot(x - 150.0, y - 150.0) <= 45) pixels[y * size + x] = 15
            }
        }
        assertNull(
            "strict mode must not find a target where there is no sheet",
            TargetLocator.locate(pixels, size, size, strict = true),
        )
    }

    @Test
    fun `strict mode rejects a mark far off centre`() {
        // A sheet with its mark in the corner — a target in the frame, but not
        // the one being aimed at.
        val size = 400
        val pixels = IntArray(size * size) { 25 }
        for (y in 0 until size) {
            for (x in 0 until size) {
                if (x in 40..360 && y in 40..360) pixels[y * size + x] = 235
                if (hypot(x - 90.0, y - 90.0) <= 40) pixels[y * size + x] = 20
            }
        }
        assertNull(
            "a mark in the corner is not what the camera is aimed at",
            TargetLocator.locate(pixels, size, size, strict = true),
        )
    }

    @Test
    fun `strict mode accepts a properly framed target`() {
        val (pixels, width, height) = sheetOnBackstop(markRadius = 42)
        val fit = TargetLocator.locate(pixels, width, height, strict = true)
        assertNotNull("a centred, well-lit target must still be found", fit)
        assertEquals(42.0, fit!!.major, 6.0)
    }

    @Test
    fun `strict mode rejects a moderately squashed ellipse too`() {
        // Not a 5:1 smear — a 2:1 oval, the shape a shadow or a bench edge makes.
        // The earlier 0.55 threshold let these through, and they are what showed
        // up in the viewfinder as a wildly distorted "target".
        val size = 400
        val pixels = IntArray(size * size) { 25 }
        for (y in 0 until size) {
            for (x in 0 until size) {
                if (x in 40..360 && y in 40..360) pixels[y * size + x] = 235
                val dx = (x - 200) / 80.0
                val dy = (y - 200) / 40.0
                if (dx * dx + dy * dy <= 1.0) pixels[y * size + x] = 20
            }
        }
        assertNull(
            "a 2:1 oval is not a target seen from the front",
            TargetLocator.locate(pixels, size, size, strict = true),
        )
    }

    @Test
    fun `strict mode rejects a badly squashed ellipse`() {
        // A sheet with a long dark smear across it — a shadow, not a mark.
        val size = 400
        val pixels = IntArray(size * size) { 25 }
        for (y in 0 until size) {
            for (x in 0 until size) {
                if (x in 40..360 && y in 40..360) pixels[y * size + x] = 235
                val dx = (x - 200) / 110.0
                val dy = (y - 200) / 22.0
                if (dx * dx + dy * dy <= 1.0) pixels[y * size + x] = 20
            }
        }
        assertNull(
            "a 5:1 smear is a shadow, not an aiming mark",
            TargetLocator.locate(pixels, size, size, strict = true),
        )
    }

    @Test
    fun `the lenient path still accepts what strict mode turns away`() {
        // The two modes must genuinely differ, or `strict` is decoration.
        val size = 300
        val pixels = IntArray(size * size) { 60 }
        for (y in 100 until 200) {
            for (x in 100 until 200) {
                if (hypot(x - 150.0, y - 150.0) <= 45) pixels[y * size + x] = 15
            }
        }
        assertNotNull(
            "the deliberate-photo path keeps guessing",
            TargetLocator.locate(pixels, size, size, strict = false),
        )
    }


    @Test
    fun `the frame clears ring 1 but stays on the sheet`() {
        // A shot on ring 1's outer edge sits at 1.0 and must be placeable, so
        // the frame has to clear it with room to grab the marker.
        assertTrue(
            "frame must extend past ring 1",
            TargetGeometry.FRAME_TO_SCORING >= 1.10,
        )
        // And it must stay inside the paper: 600 mm of sheet over a 500 mm
        // scoring area is 1.2 scoring radii, so anything past that puts backstop
        // in every crop. A miss is recorded from the shot list, not by placing
        // it on paper the shot never touched, so nothing needs room out there.
        assertTrue(
            "frame must stay within a 600 mm sheet",
            TargetGeometry.FRAME_TO_SCORING <= 600.0 / 500.0,
        )
    }



    @Test
    fun `strict mode rejects a pale backstop merged with the sheet`() {
        // The failure from the range: a light-coloured backstop is nearly as
        // bright as the paper, both end up in one mask, and the "sheet" then
        // reaches far above the target. Nothing objected, because the mask was
        // large, bright and contained a perfectly good aiming mark — just not in
        // its middle. That is what gives it away.
        val size = 400
        val pixels = IntArray(size * size) { 20 }
        for (y in 0 until size) {
            for (x in 0 until size) {
                // A backstop exactly as bright as the paper. No threshold can
                // separate them — the two merge into one mask, which is the
                // failure photographed at the range.
                if (x in 40..360 && y in 40..200) pixels[y * size + x] = 240
                // The sheet below it.
                if (x in 60..340 && y in 200..360) pixels[y * size + x] = 240
                // The mark, centred on the SHEET — far below the merged centre.
                if (hypot(x - 200.0, y - 280.0) <= 45) pixels[y * size + x] = 20
            }
        }
        assertNull(
            "a mark sitting low in the mask means the mask is not a sheet",
            TargetLocator.locate(pixels, size, size, strict = true),
        )
    }

    @Test
    fun `strict mode still accepts a mark centred on its sheet`() {
        // The same construction, but with the backstop dark enough to be
        // excluded — the everyday case must keep working.
        val (pixels, width, height) = sheetOnBackstop(markRadius = 42)
        assertNotNull(
            "a centred mark on a rectangular sheet must pass",
            TargetLocator.locate(pixels, width, height, strict = true),
        )
    }

    // --- The viewfinder outline ---

    /**
     * The case the range actually presents, and the reason the viewfinder stopped
     * tracing the sheet's edge: a backstop that photographs as bright as the
     * paper. The outline must still sit on the target, because it is measured
     * from the aiming mark rather than searched for.
     */
    @Test
    fun `the crop outline holds when the backstop is as bright as the paper`() {
        val (pixels, width, height) = sheetOnBackstop(backstop = 215)
        val outline = checkNotNull(
            TargetLocator.findCropOutline(pixels, width, height, blackRatio = 0.4),
        ) { "no aiming mark found" }

        // The mark is 42 px for a 0.4 black ratio, so ring 1 is 105 px and the
        // crop reaches 1.15 of that — 121 px from the centre, inside the paper's
        // 120 to within a pixel and well short of the backstop's 170. Tracing
        // brightness lands on the backstop instead.
        for ((name, corner) in listOf(
            "topLeft" to outline.topLeft,
            "topRight" to outline.topRight,
            "bottomRight" to outline.bottomRight,
            "bottomLeft" to outline.bottomLeft,
        )) {
            val dx = abs(corner.first - width / 2)
            val dy = abs(corner.second - height / 2)
            assertEquals("$name x at $corner", 121.0, dx.toDouble(), 6.0)
            assertEquals("$name y at $corner", 121.0, dy.toDouble(), 6.0)
        }
    }

    /**
     * Pins the limit the outline was changed away from, so nobody puts the
     * viewfinder back on it: rays walking out from the mark cannot find paper's
     * edge when the backstop is nearly as bright.
     */
    @Test
    fun `tracing the sheet edge fails on a bright backstop`() {
        val (pixels, width, height) = sheetOnBackstop(backstop = 215)
        val quad = TargetLocator.findSheetQuad(pixels, width, height)
        val corners = quad?.let {
            listOf(it.topLeft, it.topRight, it.bottomRight, it.bottomLeft)
        }
        // Either it gives up, or it runs past the paper onto the backstop.
        assertTrue(
            "expected the sheet trace to overrun the paper, got $corners",
            corners == null || corners.any { (x, y) ->
                abs(x - width / 2) > 140 || abs(y - height / 2) > 140
            },
        )
    }

    @Test
    fun `the sheet quad follows the paper, not the backstop`() {
        val (pixels, width, height) = sheetOnBackstop()
        val quad = checkNotNull(TargetLocator.findSheetQuad(pixels, width, height)) {
            "no sheet found"
        }
        // Paper spans 80..320 in a 400px frame; the backstop reaches 30..370.
        for ((name, corner) in listOf(
            "topLeft" to quad.topLeft,
            "topRight" to quad.topRight,
            "bottomRight" to quad.bottomRight,
            "bottomLeft" to quad.bottomLeft,
        )) {
            assertTrue(
                "$name at $corner is outside the paper — the backstop was traced",
                corner.first in 70..330 && corner.second in 70..330,
            )
        }
    }

    @Test
    fun `corners land in their own quadrants`() {
        val (pixels, width, height) = sheetOnBackstop()
        val quad = checkNotNull(TargetLocator.findSheetQuad(pixels, width, height))
        assertTrue("top left", quad.topLeft.first < width / 2 && quad.topLeft.second < height / 2)
        assertTrue("top right", quad.topRight.first > width / 2 && quad.topRight.second < height / 2)
        assertTrue(
            "bottom right",
            quad.bottomRight.first > width / 2 && quad.bottomRight.second > height / 2,
        )
        assertTrue(
            "bottom left",
            quad.bottomLeft.first < width / 2 && quad.bottomLeft.second > height / 2,
        )
    }

    @Test
    fun `a distant sheet is reported as too small to measure`() {
        // A sheet covering about 15% of the frame: found, but too far away to
        // measure — the aiming mark is only a few dozen pixels across, and the
        // scale from that is guesswork. The app asks for a step closer instead.
        //
        // A printed target and not a blank rectangle, because the outline is
        // walked out from the aiming mark: no mark, no outline. That is
        // deliberate — a green frame around a sheet of paper that is not a
        // target would be worse than no frame.
        val (pixels, width, height) = sheetOnBackstop(size = 600, sheetHalf = 115, markRadius = 40)
        val quad = checkNotNull(TargetLocator.findSheetQuad(pixels, width, height)) {
            "a 230x230 target in a 600x600 frame should still be found"
        }
        assertTrue(
            "covers ${"%.0f".format(quad.areaFraction * 100)}% — not close enough",
            !quad.closeEnough,
        )
    }

    @Test
    fun `the outline lands on the sheet's edge`() {
        // What the outline is for is telling the shooter what has been
        // recognised, so the one thing it must not do is cut across the target.
        // Its predecessor did exactly that on three of four real photographs,
        // because it thresholded brightness and the lower half of a sheet is
        // nearly always in shadow (ml/NOTES-real-targets.md §5b).
        val size = 400
        val sheetHalf = 120
        val (pixels, width, height) = sheetOnBackstop(size = size, sheetHalf = sheetHalf)
        val quad = checkNotNull(TargetLocator.findSheetQuad(pixels, width, height))

        val centre = size / 2
        val corners = listOf(
            centre - sheetHalf to centre - sheetHalf,
            centre + sheetHalf to centre - sheetHalf,
            centre + sheetHalf to centre + sheetHalf,
            centre - sheetHalf to centre + sheetHalf,
        )
        val found = listOf(quad.topLeft, quad.topRight, quad.bottomRight, quad.bottomLeft)
        for ((expected, actual) in corners.zip(found)) {
            val off = hypot(
                (expected.first - actual.first).toDouble(),
                (expected.second - actual.second).toDouble(),
            )
            assertTrue(
                "corner $expected came out at $actual, ${"%.0f".format(off)}px away",
                off <= 12.0,
            )
        }
    }

    @Test
    fun `a sheet filling the frame is close enough`() {
        val (pixels, width, height) = sheetOnBackstop()
        val quad = checkNotNull(TargetLocator.findSheetQuad(pixels, width, height))
        assertTrue("240x240 of a 400x400 frame should qualify", quad.closeEnough)
    }

    @Test
    fun `no sheet means no outline`() {
        val size = 200
        val pixels = IntArray(size * size) { 30 }
        assertNull(TargetLocator.findSheetQuad(pixels, size, size))
    }

    // --- Building blocks ---

    @Test
    fun `otsu splits a two-peaked histogram between the peaks`() {
        val values = IntArray(1000) { if (it < 500) 40 else 200 }
        val level = TargetLocator.otsu(values)
        // The split is `value > level`, so the darker peak must fall below it
        // and the brighter one above.
        assertTrue("threshold $level must separate 40 from 200", level in 40..199)
        assertTrue("dark peak on the dark side", 40 <= level)
        assertTrue("bright peak on the bright side", 200 > level)
    }

    @Test
    fun `holes get filled`() {
        // A ring, like the aiming mark with its light ten in the middle.
        val size = 40
        val mask = BooleanArray(size * size)
        for (y in 0 until size) {
            for (x in 0 until size) {
                val r = hypot(x - 19.5, y - 19.5)
                mask[y * size + x] = r in 6.0..15.0
            }
        }
        val before = mask.count { it }
        val after = TargetLocator.fillHoles(mask, size, size).count { it }
        // A ring of r 6..15 covers pi*(15^2-6^2) and fills to pi*15^2 — about a
        // fifth more, not the half an earlier version of this test demanded.
        val filledDisc = Math.PI * 15.0 * 15.0
        assertTrue("filling should add the interior ($before -> $after)", after > before)
        assertEquals("filled area", filledDisc, after.toDouble(), filledDisc * 0.06)
    }

    @Test
    fun `a filled circle fits its own radius`() {
        val size = 100
        val radius = 30.0
        val mask = BooleanArray(size * size)
        for (y in 0 until size) {
            for (x in 0 until size) {
                mask[y * size + x] = hypot(x - 49.5, y - 49.5) <= radius
            }
        }
        val fit = checkNotNull(TargetLocator.fitEllipse(mask, size, size))
        assertEquals("centre x", 49.5, fit.cx, 0.5)
        assertEquals("centre y", 49.5, fit.cy, 0.5)
        assertEquals("radius", radius, fit.major, radius * 0.03)
        assertEquals("circularity", 1.0, fit.circularity, 0.02)
    }

    @Test
    fun `labelling separates disconnected blobs`() {
        val size = 20
        val mask = BooleanArray(size * size)
        mask[0] = true
        mask[1] = true
        mask[size * 10 + 10] = true
        val labelling = TargetLocator.label(mask, size, size)
        assertEquals(2, labelling.count)
    }
}
