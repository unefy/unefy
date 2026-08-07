package com.unefy.core.model.scoring

import kotlin.math.sqrt
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Mirror of `backend/tests/test_scoring.py`.
 *
 * Same inputs, same expected outputs. Two engines score the same shots — one
 * here, one in Python — and the server's value is the one that gets stored, so a
 * divergence shows up as a member disputing a result rather than as a failing
 * build. These paired tests are what prevent that. A case added on either side
 * belongs on both.
 */
class ScoringEngineTest {

    private val precision = TargetGeometrySeed.PRECISION_25M
    private val airRifle = TargetGeometrySeed.AIR_RIFLE_10M

    /** Normalised radius for a distance given in millimetres. */
    private fun TargetGeometry.atMm(distanceMm: Double) = distanceMm / scoringRadiusMm

    // --- Basic ring boundaries ---

    @Test
    fun `dead centre is a ten`() {
        assertEquals(10, ScoringEngine.ringFor(0.0, precision))
    }

    @Test
    fun `outside ring one is a miss`() {
        assertEquals(0, ScoringEngine.ringFor(precision.atMm(260.0), precision, 9.0))
    }

    @Test
    fun `every ring is reachable`() {
        val seen = (10 downTo 1).map { ring ->
            val outer = precision.ringRadiusMm(ring)
            val inner = if (ring < 10) precision.ringRadiusMm(ring + 1) else 0.0
            ScoringEngine.ringFor(precision.atMm((outer + inner) / 2), precision, 0.001)
        }
        assertEquals(listOf(10, 9, 8, 7, 6, 5, 4, 3, 2, 1), seen)
    }

    // --- Scoring by the bullet edge ---

    @Test
    fun `hole touching the line scores the higher ring`() {
        // Ring 10 radius is 25 mm; a 9 mm bullet at 29 mm reaches 24.5 mm.
        assertEquals(10, ScoringEngine.ringFor(precision.atMm(29.0), precision, 9.0))
    }

    @Test
    fun `the same shot with a smaller calibre scores lower`() {
        // 29 - 2.8 = 26.2 mm, outside ring 10. Why the caliber has to be right.
        assertEquals(9, ScoringEngine.ringFor(precision.atMm(29.0), precision, 5.6))
    }

    @Test
    fun `a shot just outside ring one is saved by its calibre`() {
        assertEquals(1, ScoringEngine.ringFor(precision.atMm(255.0), precision, 11.5))
    }

    @Test
    fun `negative distance is treated as a radius`() {
        assertEquals(10, ScoringEngine.ringFor(-precision.atMm(29.0), precision, 9.0))
    }

    // --- Air rifle: the hard case ---

    @Test
    fun `air rifle ten is smaller than the pellet`() {
        assertEquals(0.25, airRifle.ringRadiusMm(10), 1e-9)
        assertEquals(10, ScoringEngine.ringFor(airRifle.atMm(2.4), airRifle))
        assertEquals(9, ScoringEngine.ringFor(airRifle.atMm(2.8), airRifle))
    }

    @Test
    fun `air rifle outer ring`() {
        assertEquals(1, ScoringEngine.ringFor(airRifle.atMm(24.0), airRifle))
        assertEquals(0, ScoringEngine.ringFor(airRifle.atMm(26.0), airRifle))
    }

    // --- Inner ten ---

    @Test
    fun `inner ten is stricter than a ten`() {
        assertTrue(ScoringEngine.isInnerTen(precision.atMm(16.0), precision, 9.0))
        assertFalse(ScoringEngine.isInnerTen(precision.atMm(20.0), precision, 9.0))
        assertEquals(10, ScoringEngine.ringFor(precision.atMm(20.0), precision, 9.0))
    }

    // --- Series scoring ---

    @Test
    fun `score totals the rings`() {
        val result = ScoringEngine.score(List(5) { ShotInput(0.0, 0.0) }, precision, 9.0)
        assertEquals(50, result.total)
        assertEquals(listOf(10, 10, 10, 10, 10), result.rings)
        assertEquals(5, result.innerTens)
    }

    @Test
    fun `a shot may override the series calibre`() {
        // Two members, two calibers, one sheet — the case from the range.
        val position = precision.atMm(29.0)
        val result = ScoringEngine.score(
            listOf(
                ShotInput(position, 0.0),
                ShotInput(position, 0.0, caliberMm = 5.6),
            ),
            precision,
            caliberMm = 9.0,
        )
        assertEquals(listOf(10, 9), result.rings)
        assertEquals(listOf(9.0, 5.6), result.shots.map { it.caliberMm })
    }

    @Test
    fun `series falls back to the targets default calibre`() {
        val result = ScoringEngine.score(listOf(ShotInput(precision.atMm(29.0), 0.0)), precision)
        assertEquals(precision.defaultCaliberMm, result.shots[0].caliberMm, 1e-9)
    }

    @Test
    fun `empty series scores zero`() {
        val result = ScoringEngine.score(emptyList(), precision)
        assertEquals(0, result.total)
        assertNull(result.groupingMm)
    }

    // --- Grouping ---

    @Test
    fun `grouping is outside to outside`() {
        val offset = precision.atMm(50.0)
        val result = ScoringEngine.score(
            listOf(ShotInput(-offset, 0.0), ShotInput(offset, 0.0)),
            precision,
            9.0,
        )
        assertEquals(109.0, result.groupingMm!!, 0.01)
    }

    @Test
    fun `grouping uses each shots own calibre`() {
        val offset = precision.atMm(50.0)
        val result = ScoringEngine.score(
            listOf(
                ShotInput(-offset, 0.0, caliberMm = 9.0),
                ShotInput(offset, 0.0, caliberMm = 5.6),
            ),
            precision,
        )
        assertEquals(100 + 4.5 + 2.8, result.groupingMm!!, 0.01)
    }

    @Test
    fun `grouping ignores a shot that missed the sheet`() {
        // The same case as `test_grouping_ignores_a_shot_that_missed_the_sheet`
        // in backend/tests/test_scoring.py. A shot off the paper has no
        // measured position — the shooter reported it, nobody looked at a hole
        // — so it says how badly it went, not how tight the group is.
        val geometry = TargetGeometrySeed.DEFAULT
        val offset = 50.0 / geometry.scoringRadiusMm
        val tight = listOf(ShotInput(-offset, 0.0), ShotInput(offset, 0.0))
        val withMiss = tight + ShotInput(0.0, 1.4)

        val scored = ScoringEngine.score(withMiss, geometry, caliberMm = 9.0)
        assertEquals(109.0, scored.groupingMm!!, 0.01)

        // It is still a shot, and it is still scored — as a zero.
        assertEquals(3, scored.shots.size)
        assertEquals(0, scored.shots.last().ring)
    }

    @Test
    fun `grouping needs two shots`() {
        assertNull(ScoringEngine.groupingMm(emptyList(), precision))
        assertNull(ScoringEngine.score(listOf(ShotInput(0.0, 0.0)), precision).groupingMm)
    }

    // --- Geometry invariants ---

    @Test
    fun `geometry rejects the wrong number of rings`() {
        assertThrows(IllegalArgumentException::class.java) {
            precision.copy(ringDiametersMm = listOf(10.0, 20.0))
        }
    }

    @Test
    fun `geometry rejects unsorted rings`() {
        // Guards against the ordering mistake that made the iOS tables wrong.
        assertThrows(IllegalArgumentException::class.java) {
            precision.copy(ringDiametersMm = precision.ringDiametersMm.reversed())
        }
    }

    @Test
    fun `diagonal distance is euclidean`() {
        val radius = precision.atMm(100.0)
        val straight = ScoringEngine.score(listOf(ShotInput(radius, 0.0)), precision, 9.0)
        val component = radius / sqrt(2.0)
        val diagonal =
            ScoringEngine.score(listOf(ShotInput(component, component)), precision, 9.0)
        assertEquals(straight.rings, diagonal.rings)
    }
}

/**
 * The seed is the thing most likely to be wrong, so it gets checked rather than
 * trusted — wrong ring tables are exactly why the earlier prototype misscored.
 */
class TargetGeometrySeedTest {

    @Test
    fun `every seeded target is self consistent`() {
        for (geometry in TargetGeometrySeed.ALL) {
            assertTrue(
                "${geometry.slug}: inner ten larger than ring 10",
                geometry.innerTenDiameterMm <= geometry.ringDiametersMm.first(),
            )
            assertTrue(
                "${geometry.slug}: black outside the scoring area",
                geometry.blackDiameterMm <= geometry.ringDiametersMm.last(),
            )
            assertEquals("${geometry.slug}: ring 1 is the reference radius",
                1.0, geometry.ringFraction(1), 1e-9)
            assertEquals(
                "${geometry.slug}: dead centre must be a ten",
                10,
                ScoringEngine.ringFor(0.0, geometry),
            )
        }
    }

    @Test
    fun `slugs are unique`() {
        val slugs = TargetGeometrySeed.ALL.map { it.slug }
        assertEquals(slugs.size, slugs.toSet().size)
    }

    @Test
    fun `lookup by slug finds every seeded target`() {
        for (geometry in TargetGeometrySeed.ALL) {
            assertEquals(geometry, TargetGeometrySeed.bySlug(geometry.slug))
        }
        assertNull(TargetGeometrySeed.bySlug("does_not_exist"))
    }

    @Test
    fun `the black is drawn over the rings it covers`() {
        // Scheibe Nr. 5: black is 200 mm, which is ring 7's outer diameter.
        val precision = TargetGeometrySeed.PRECISION_25M
        assertTrue(precision.isRingOnBlack(7))
        assertFalse(precision.isRingOnBlack(6))
    }

    @Test
    fun `calibers cover the clubs main disciplines`() {
        // Large-bore 25 m precision is the main activity; .22 shares the sheet.
        assertEquals(9.0, Calibers.byDiameter(9.0)!!.diameterMm, 1e-9)
        assertEquals(".22 lfB (5,6 mm)", Calibers.byDiameter(5.6)!!.name)
    }
}
