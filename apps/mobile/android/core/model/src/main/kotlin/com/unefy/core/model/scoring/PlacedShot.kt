package com.unefy.core.model.scoring

import kotlin.math.hypot

/**
 * A shot on the target while it is being edited.
 *
 * Distinct from [ScoredShot] only by carrying an [id]: the canvas needs a stable
 * identity to move or delete one shot out of ten that may sit on top of each
 * other. The id never leaves the device — the wire format is positional.
 */
data class PlacedShot(
    val id: String,
    val x: Double,
    val y: Double,
    val ring: Int = 0,
    val innerTen: Boolean = false,
    /** Set only when this shot's caliber differs from the series default. */
    val caliberMm: Double? = null,
    /**
     * Where this shot came from: `scan` for one the photo detector proposed,
     * `manual` for one a person placed or corrected.
     *
     * It travels all the way to the stored record, per shot, because that turns
     * every recorded series into a measurement of the detector against a real
     * sheet — proposed against what actually counted — without anybody
     * annotating anything twice.
     */
    val source: String = SOURCE_MANUAL,
) {
    /**
     * True when this is a shot that missed the sheet altogether.
     *
     * There is no hole to point at, so it has a conventional position rather
     * than a measured one, past the printed sheet. Both scoring engines leave
     * it out of the group size for that reason.
     */
    val isMiss: Boolean get() = hypot(x, y) > TargetGeometry.FRAME_TO_SCORING
}

const val SOURCE_MANUAL = "manual"
const val SOURCE_SCAN = "scan"

/**
 * A whole series being edited, kept scored at all times.
 *
 * The running total is what the shooter watches while placing shots, so scoring
 * happens on every edit rather than on save. It is cheap — ten shots against a
 * ten-entry table — and it means the number on screen can never disagree with
 * the number that gets stored.
 */
/**
 * Where a shot that missed the sheet is filed, in normalised coordinates.
 *
 * Beyond FRAME_TO_SCORING, so it is outside the printed sheet by definition.
 * The backend's schema allows up to 1.5.
 */
const val MISS_Y = 1.4

data class ShotSeriesDraft(
    val geometry: TargetGeometry,
    val caliberMm: Double,
    val shots: List<PlacedShot> = emptyList(),
) {
    val total: Int get() = shots.sumOf { it.ring }
    val innerTens: Int get() = shots.count { it.innerTen }

    val groupingMm: Double?
        get() = ScoringEngine.groupingMm(
            shots.map {
                ScoredShot(it.x, it.y, it.ring, it.innerTen, it.caliberMm ?: caliberMm)
            },
            geometry,
        )

    /** Add a shot at a normalised position, scored immediately. */
    fun place(
        id: String,
        x: Double,
        y: Double,
        caliberMm: Double? = null,
        source: String = SOURCE_MANUAL,
    ): ShotSeriesDraft =
        copy(shots = shots + scored(PlacedShot(id, x, y, caliberMm = caliberMm, source = source)))

    /**
     * Add a shot that missed the sheet completely.
     *
     * It happens, it counts as a zero, and until now it could not be recorded
     * at all: there is nothing to point at on the target, so a shooter with ten
     * shots and nine holes had to save a series of nine. The position is a
     * convention rather than a measurement — past the printed sheet, so it
     * scores zero on its own and both scoring engines leave it out of the group
     * size (see `ScoringEngine.groupingMm`).
     */
    fun placeMiss(id: String, caliberMm: Double? = null): ShotSeriesDraft =
        place(id, 0.0, MISS_Y, caliberMm)

    /**
     * Move an existing shot, rescoring it at the new position.
     *
     * Moving one the detector proposed makes it the shooter's. The pair
     * (proposed, corrected) is the whole point of recording where a shot came
     * from, and a shot that has been dragged is no longer evidence of what the
     * detector found.
     */
    fun move(id: String, x: Double, y: Double): ShotSeriesDraft =
        copy(
            shots = shots.map {
                if (it.id == id) scored(it.copy(x = x, y = y, source = SOURCE_MANUAL)) else it
            },
        )

    fun remove(id: String): ShotSeriesDraft = copy(shots = shots.filterNot { it.id == id })

    /** Rescore everything — after the caliber or the target type changed. */
    fun rescored(): ShotSeriesDraft = copy(shots = shots.map(::scored))

    private fun scored(shot: PlacedShot): PlacedShot {
        val effective = shot.caliberMm ?: caliberMm
        val distance = kotlin.math.hypot(shot.x, shot.y)
        return shot.copy(
            ring = ScoringEngine.ringFor(distance, geometry, effective),
            innerTen = ScoringEngine.isInnerTen(distance, geometry, effective),
        )
    }

    /** The nearest shot to a point, if one is within [radius] of it. */
    fun nearest(x: Double, y: Double, radius: Double): PlacedShot? =
        shots
            .map { it to kotlin.math.hypot(it.x - x, it.y - y) }
            .filter { (_, distance) -> distance <= radius }
            .minByOrNull { (_, distance) -> distance }
            ?.first
}
