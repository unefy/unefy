package com.unefy.core.model.scoring

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The editing logic behind the interactive target.
 *
 * Kept out of the composable on purpose: placing, moving and deleting shots is
 * where the bugs live, and here it is testable without a device.
 */
class ShotSeriesDraftTest {

    private val precision = TargetGeometrySeed.PRECISION_25M

    private fun draft(caliberMm: Double = 9.0) =
        ShotSeriesDraft(geometry = precision, caliberMm = caliberMm)

    private fun atMm(distanceMm: Double) = distanceMm / precision.scoringRadiusMm

    @Test
    fun `a placed shot is scored immediately`() {
        val result = draft().place("a", 0.0, 0.0)
        assertEquals(1, result.shots.size)
        assertEquals(10, result.shots[0].ring)
        assertTrue(result.shots[0].innerTen)
        assertEquals(10, result.total)
    }

    @Test
    fun `moving a shot rescores it`() {
        val placed = draft().place("a", 0.0, 0.0)
        assertEquals(10, placed.total)

        val moved = placed.move("a", atMm(240.0), 0.0)
        assertEquals(1, moved.total)
        assertEquals(1, moved.shots.size)
    }

    @Test
    fun `moving an unknown id changes nothing`() {
        val placed = draft().place("a", 0.0, 0.0)
        assertEquals(placed, placed.move("nope", 0.5, 0.5))
    }

    @Test
    fun `removing a shot drops it from the total`() {
        val two = draft().place("a", 0.0, 0.0).place("b", 0.0, 0.0)
        assertEquals(20, two.total)

        val one = two.remove("a")
        assertEquals(10, one.total)
        assertEquals(listOf("b"), one.shots.map { it.id })
    }

    @Test
    fun `nearest finds a shot inside the grab radius`() {
        val placed = draft().place("a", 0.1, 0.1)
        assertNotNull(placed.nearest(0.11, 0.11, radius = 0.05))
        assertNull(placed.nearest(0.4, 0.4, radius = 0.05))
    }

    @Test
    fun `nearest picks the closest when shots overlap`() {
        // Ten shots in the middle sit on top of each other; grabbing must be
        // predictable or the user deletes the wrong one.
        val placed = draft().place("far", 0.05, 0.0).place("near", 0.01, 0.0)
        assertEquals("near", placed.nearest(0.012, 0.0, radius = 0.1)?.id)
    }

    @Test
    fun `changing the calibre rescores the whole series`() {
        // The real case: a series entered as 9 mm turns out to have been .22.
        // Ring 10 radius is 25 mm and the shots sit at 29 mm.
        val position = atMm(29.0)
        val asLargeBore = draft(caliberMm = 9.0).place("a", position, 0.0)
        assertEquals(10, asLargeBore.shots[0].ring)

        val asSmallBore = asLargeBore.copy(caliberMm = 5.6).rescored()
        assertEquals(9, asSmallBore.shots[0].ring)
    }

    @Test
    fun `a shot keeps its own calibre when the series default changes`() {
        val position = atMm(29.0)
        val mixed = draft(caliberMm = 9.0)
            .place("gk", position, 0.0)
            .place("kk", position, 0.0, caliberMm = 5.6)

        assertEquals(listOf(10, 9), mixed.shots.map { it.ring })

        // Series default drops to .22; only the shot without its own caliber moves.
        val rescored = mixed.copy(caliberMm = 5.6).rescored()
        assertEquals(listOf(9, 9), rescored.shots.map { it.ring })
    }

    @Test
    fun `changing the target type rescores against the new geometry`() {
        // Both targets have ten evenly spaced rings, so a normalised position
        // lands in nearly the same ring on either — what differs is how much the
        // bullet edge is worth. A 4.5 mm pellet is a tenth of the air rifle
        // sheet; a 9 mm bullet is under two hundredths of the 25 m sheet. At
        // 0.53 that gap is enough to change the ring.
        val onPrecision = draft().place("a", 0.53, 0.0)
        assertEquals(5, onPrecision.shots[0].ring)

        val onAirRifle = onPrecision
            .copy(geometry = TargetGeometrySeed.AIR_RIFLE_10M, caliberMm = 4.5)
            .rescored()
        assertEquals(6, onAirRifle.shots[0].ring)
    }

    @Test
    fun `an empty draft has no grouping and no score`() {
        val empty = draft()
        assertEquals(0, empty.total)
        assertEquals(0, empty.innerTens)
        assertNull(empty.groupingMm)
    }

    @Test
    fun `grouping matches the engine`() {
        val offset = atMm(50.0)
        val two = draft().place("a", -offset, 0.0).place("b", offset, 0.0)
        assertEquals(109.0, two.groupingMm!!, 0.01)
    }

    @Test
    fun `inner tens are counted separately from tens`() {
        val series = draft()
            .place("inner", atMm(16.0), 0.0) // reaches 11.5 mm — inner ten
            .place("outer", atMm(20.0), 0.0) // reaches 15.5 mm — a ten, not inner
        assertEquals(20, series.total)
        assertEquals(1, series.innerTens)
    }

    @Test
    fun `a miss counts as zero but keeps its position`() {
        val missed = draft().place("a", atMm(280.0), 0.0)
        assertEquals(0, missed.total)
        assertEquals(1, missed.shots.size)
        assertEquals(atMm(280.0), missed.shots[0].x, 1e-9)
    }
}
