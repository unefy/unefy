package com.unefy.feature.scoring

import com.unefy.core.model.scoring.TargetGeometrySeed
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Combining the offline queue with the server-backed cache.
 *
 * Tested directly rather than through the repository, which would need Room: the
 * rule is pure list logic, and the interesting case — the same series in both
 * lists at once — is a timing window that is awkward to reproduce otherwise.
 */
class MergeSeriesTest {

    @Test
    fun `queued series come first`() {
        val merged = mergeSeries(
            pending = listOf(series("queued", pending = true)),
            cached = listOf(series("sent", pending = false)),
        )
        assertEquals(listOf("queued", "sent"), merged.map { it.id })
    }

    @Test
    fun `a series present in both is shown once, as the queued copy`() {
        // The window between a successful send and the next refresh. Showing
        // both would look to the shooter like they recorded the series twice.
        val merged = mergeSeries(
            pending = listOf(series("s1", pending = true)),
            cached = listOf(series("s1", pending = false)),
        )
        assertEquals(1, merged.size)
        assertTrue("the queued copy wins", merged[0].pending)
    }

    @Test
    fun `an empty queue leaves the cache untouched`() {
        val cached = listOf(series("a", false), series("b", false))
        assertEquals(cached, mergeSeries(emptyList(), cached))
    }

    @Test
    fun `an empty cache leaves the queue untouched`() {
        val pending = listOf(series("a", true))
        assertEquals(pending, mergeSeries(pending, emptyList()))
    }

    private fun series(id: String, pending: Boolean) = ShotSeries(
        id = id,
        memberId = "m1",
        memberLabel = null,
        discipline = null,
        targetTypeSlug = TargetGeometrySeed.PRECISION_25M.slug,
        caliberMm = 9.0,
        total = 87,
        innerTens = null,
        groupingMm = null,
        shots = emptyList(),
        recordedAt = "2026-08-05T18:30:00Z",
        notes = null,
        pending = pending,
    )
}
