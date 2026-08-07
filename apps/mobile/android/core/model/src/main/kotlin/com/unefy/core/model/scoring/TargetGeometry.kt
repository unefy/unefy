package com.unefy.core.model.scoring

import kotlin.math.abs
import kotlin.math.hypot

/**
 * Ring geometry of one shooting target, in millimetres.
 *
 * This is the Kotlin half of a pair: `backend/app/services/scoring.py` holds the
 * same rules in Python, and the server recomputes every ring it is sent. The two
 * must agree — where they do not, the server wins and logs the difference, which
 * is the only warning anybody gets that they have drifted apart. Any test added
 * to `backend/tests/test_scoring.py` belongs in [ScoringEngineTest] as well.
 *
 * Coordinate convention, shared with the backend:
 *
 * > x, y are normalised to the RING 1 RADIUS, origin at the target centre, y
 * > pointing down (screen coordinates). (0, 0) is dead centre; a magnitude of
 * > 1.0 sits exactly on the outer edge of ring 1.
 *
 * @param ringDiametersMm outer diameters, index 0 = ring 10 … index 9 = ring 1.
 */
data class TargetGeometry(
    val slug: String,
    val name: String,
    val ringDiametersMm: List<Double>,
    val innerTenDiameterMm: Double,
    /**
     * Diameter of the black aiming mark.
     *
     * A length rather than "black from ring N" because the ISSF 50 m rifle black
     * (112.4 mm) falls between two rings. It is also the scale anchor for photo
     * recognition, which needs the exact physical value.
     */
    val blackDiameterMm: Double,
    /** Default only — overridable per series and per shot. */
    val defaultCaliberMm: Double,
    val caliberName: String?,
    val distanceM: Int,
) {
    init {
        require(ringDiametersMm.size == RING_COUNT) {
            "$slug: expected $RING_COUNT ring diameters, got ${ringDiametersMm.size}"
        }
        require(ringDiametersMm.zipWithNext().all { (a, b) -> a < b }) {
            "$slug: ring diameters must increase from ring 10 to ring 1"
        }
    }

    /** Radius of ring 1 — the reference length for normalised coordinates. */
    val scoringRadiusMm: Double get() = ringDiametersMm.last() / 2.0

    /** Outer radius of [ring] in mm. Ring 10 is the innermost. */
    fun ringRadiusMm(ring: Int): Double = ringDiametersMm[RING_COUNT - ring] / 2.0

    /** Outer radius of [ring] as a fraction of the scoring radius (0…1). */
    fun ringFraction(ring: Int): Double = ringRadiusMm(ring) / scoringRadiusMm

    /** Fraction of the scoring radius covered by the black. Drives the canvas. */
    val blackFraction: Double get() = (blackDiameterMm / 2.0) / scoringRadiusMm

    val innerTenFraction: Double get() = (innerTenDiameterMm / 2.0) / scoringRadiusMm

    /**
     * The outermost ring whose line still falls on the black.
     *
     * What the photo detection actually measures is the black mark, so this is
     * the ring its outline corresponds to — on Scheibe Nr. 5 the black is
     * 200 mm, which is ring 7 exactly.
     */
    val blackRing: Int
        get() = (1..RING_COUNT).lastOrNull { isRingOnBlack(it) } ?: RING_COUNT

    /** Whether [ring]'s number should be drawn light, because it sits on black. */
    fun isRingOnBlack(ring: Int): Boolean = ringDiametersMm[RING_COUNT - ring] <= blackDiameterMm

    companion object {
        const val RING_COUNT = 10

        /**
         * How much wider the drawn/cropped frame is than the scoring area.
         *
         * Ring 1 does not reach the edge of a real sheet, so a frame flush with
         * it looks wrong next to a photograph. One constant, shared: the canvas
         * and the rectified crop used to carry 1.09 and 1.15 separately, and a
         * photo laid under the drawn rings could not line up however good the
         * detection was.
         *
         * Raised from 1.09 to 1.25 deliberately: nine per cent past ring 1 left
         * a shot on ring 1's outer edge only just inside the frame.
         *
         * Settled at 1.15, which is 575 mm across and therefore sits ENTIRELY
         * within a 600 mm sheet — no backstop in the crop, whatever the target
         * hangs on. 1.25 was 625 mm and carried a strip of wall or backstop in
         * every picture, 12 mm a side by construction and more once the sheet is
         * tilted. Ring 1 ends at 500 mm, so nothing scoreable is given up.
         *
         * A shot that missed the sheet altogether is no longer drawn on the
         * target — it lives in the shot list, marked as a miss, which is where
         * it belongs. Painting it on paper it never touched only ever suggested
         * a position nobody measured.
         */
        const val FRAME_TO_SCORING = 1.15
    }
}

/** One shot as placed by the user or the detector, before scoring. */
data class ShotInput(
    val x: Double,
    val y: Double,
    /** Overrides the series default. Set when one sheet carries two calibers. */
    val caliberMm: Double? = null,
)

data class ScoredShot(
    val x: Double,
    val y: Double,
    val ring: Int,
    val innerTen: Boolean,
    /** The caliber actually used, after resolving the override chain. */
    val caliberMm: Double,
) {
    val distanceFromCentre: Double get() = hypot(x, y)
}

data class SeriesScore(
    val shots: List<ScoredShot>,
    val total: Int,
    val innerTens: Int,
    val groupingMm: Double?,
) {
    val rings: List<Int> get() = shots.map { it.ring }
}

/**
 * Turns shot positions into ring values. Pure geometry, no Android dependencies.
 *
 * Scoring is by the EDGE of the bullet hole, not its centre: a hole that merely
 * touches the line scores the higher ring. That rule is why the caliber matters
 * — on the 25 m target, .22 versus 9 mm moves every boundary by ~1.7 mm, which
 * is enough to change a ring.
 *
 * The caliber is resolved per shot: `shot.caliberMm` → series default →
 * [TargetGeometry.defaultCaliberMm]. Two levels because a single sheet really
 * does carry two calibers when two members shoot the same target.
 */
object ScoringEngine {

    /** Ring value for a shot [distanceNormalized] from the centre; 0 is a miss. */
    fun ringFor(
        distanceNormalized: Double,
        geometry: TargetGeometry,
        caliberMm: Double? = null,
    ): Int {
        val caliber = caliberMm ?: geometry.defaultCaliberMm
        val distanceMm = abs(distanceNormalized) * geometry.scoringRadiusMm
        val bulletEdgeMm = maxOf(0.0, distanceMm - caliber / 2.0)

        for (ring in TargetGeometry.RING_COUNT downTo 1) {
            if (bulletEdgeMm <= geometry.ringRadiusMm(ring)) return ring
        }
        return 0
    }

    /** Whether the shot counts as an inner ten (Innenzehner), for tiebreaks. */
    fun isInnerTen(
        distanceNormalized: Double,
        geometry: TargetGeometry,
        caliberMm: Double? = null,
    ): Boolean {
        val caliber = caliberMm ?: geometry.defaultCaliberMm
        val distanceMm = abs(distanceNormalized) * geometry.scoringRadiusMm
        val bulletEdgeMm = maxOf(0.0, distanceMm - caliber / 2.0)
        return bulletEdgeMm <= geometry.innerTenDiameterMm / 2.0
    }

    /**
     * Group size (Streukreis): widest outside-to-outside spread.
     *
     * Largest centre-to-centre distance plus the two outer radii. Each shot
     * contributes its own caliber rather than assuming one, because a mixed
     * sheet may have different calibers at the extremes.
     */
    fun groupingMm(shots: List<ScoredShot>, geometry: TargetGeometry): Double? {
        // A shot that missed the sheet altogether says how badly it went, not
        // how tight the group is — and it has no measured position: nobody
        // looked at a hole, the shooter reported that one went off the paper.
        // Letting it in would let a single flyer swamp a measure that is
        // otherwise in millimetres. `backend/app/services/scoring.py` drops it
        // at the same boundary, and has to.
        val onSheet = shots.filter { hypot(it.x, it.y) <= TargetGeometry.FRAME_TO_SCORING }
        if (onSheet.size < 2) return null
        val radius = geometry.scoringRadiusMm

        var widest = 0.0
        for (i in onSheet.indices) {
            for (j in i + 1 until onSheet.size) {
                val a = onSheet[i]
                val b = onSheet[j]
                val centreToCentre = hypot(a.x - b.x, a.y - b.y) * radius
                widest = maxOf(widest, centreToCentre + a.caliberMm / 2 + b.caliberMm / 2)
            }
        }
        return kotlin.math.round(widest * 100) / 100
    }

    /** Score a whole series. [caliberMm] is the default a shot may override. */
    fun score(
        shots: List<ShotInput>,
        geometry: TargetGeometry,
        caliberMm: Double? = null,
    ): SeriesScore {
        val seriesDefault = caliberMm ?: geometry.defaultCaliberMm

        val scored = shots.map { shot ->
            val effective = shot.caliberMm ?: seriesDefault
            val distance = hypot(shot.x, shot.y)
            ScoredShot(
                x = shot.x,
                y = shot.y,
                ring = ringFor(distance, geometry, effective),
                innerTen = isInnerTen(distance, geometry, effective),
                caliberMm = effective,
            )
        }
        return SeriesScore(
            shots = scored,
            total = scored.sumOf { it.ring },
            innerTens = scored.count { it.innerTen },
            groupingMm = groupingMm(scored, geometry),
        )
    }
}
