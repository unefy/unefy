package com.unefy.core.model.scoring

/**
 * Built-in copy of the target catalog, so the app can score before it has ever
 * reached the server — which is the normal case on a range with no signal.
 *
 * The backend is the source of truth (`GET /api/v1/target-types`, seeded from
 * `backend/app/core/target_type_seeds.py`). Whatever it returns replaces these
 * values; they exist only to make a fresh install usable offline. A correction
 * to a ring diameter therefore reaches devices without an app update.
 *
 * Every number here must match the backend seed exactly — [TargetGeometrySeedTest]
 * checks the invariants, but the values themselves are only as good as the
 * federation rule they were taken from. Getting these wrong is precisely what
 * made the earlier iOS prototype produce bad scores.
 */
object TargetGeometrySeed {

    /**
     * Scheibe Nr. 5 — approved for "Pistole 25/50 m · ISSF · KK 100 m · DSU UIT
     * Präzision". One physical sheet, three entries: the ring table is identical
     * and only the distance and default caliber differ.
     *
     * This is the club's main target — 25 m large-bore precision.
     */
    private val PRECISION_RINGS =
        listOf(50.0, 100.0, 150.0, 200.0, 250.0, 300.0, 350.0, 400.0, 450.0, 500.0)

    val AIR_RIFLE_10M = TargetGeometry(
        slug = "air_rifle_10m",
        name = "Luftgewehr 10m",
        // Ring 10 is a 0.5 mm dot; every further ring adds 2.5 mm of radius.
        ringDiametersMm = listOf(0.5, 5.5, 10.5, 15.5, 20.5, 25.5, 30.5, 35.5, 40.5, 45.5),
        innerTenDiameterMm = 0.5,
        blackDiameterMm = 30.5,
        defaultCaliberMm = 4.5,
        caliberName = "4,5 mm Diabolo",
        distanceM = 10,
    )

    val AIR_PISTOL_10M = TargetGeometry(
        slug = "air_pistol_10m",
        name = "Luftpistole 10m",
        ringDiametersMm =
            listOf(11.5, 27.5, 43.5, 59.5, 75.5, 91.5, 107.5, 123.5, 139.5, 155.5),
        innerTenDiameterMm = 5.0,
        blackDiameterMm = 59.5,
        defaultCaliberMm = 4.5,
        caliberName = "4,5 mm Diabolo",
        distanceM = 10,
    )

    val SMALLBORE_RIFLE_50M = TargetGeometry(
        slug = "smallbore_rifle_50m",
        name = "KK-Gewehr 50m",
        ringDiametersMm =
            listOf(10.4, 26.4, 42.4, 58.4, 74.4, 90.4, 106.4, 122.4, 138.4, 154.4),
        innerTenDiameterMm = 5.0,
        // Deliberately not a ring boundary — that is how the target is specified.
        blackDiameterMm = 112.4,
        defaultCaliberMm = 5.6,
        caliberName = ".22 lfB (5,6 mm)",
        distanceM = 50,
    )

    val PRECISION_25M = TargetGeometry(
        slug = "sport_pistol_25m",
        name = "25m Präzision (Scheibe Nr. 5)",
        ringDiametersMm = PRECISION_RINGS,
        innerTenDiameterMm = 25.0,
        blackDiameterMm = 200.0,
        // Large bore is the common case here; .22 shooters pick their caliber.
        defaultCaliberMm = 9.0,
        caliberName = "9 mm Luger",
        distanceM = 25,
    )

    val FREE_PISTOL_50M = TargetGeometry(
        slug = "free_pistol_50m",
        name = "50m Pistole (Scheibe Nr. 5)",
        ringDiametersMm = PRECISION_RINGS,
        innerTenDiameterMm = 25.0,
        blackDiameterMm = 200.0,
        defaultCaliberMm = 5.6,
        caliberName = ".22 lfB (5,6 mm)",
        distanceM = 50,
    )

    val SMALLBORE_RIFLE_100M = TargetGeometry(
        slug = "smallbore_rifle_100m",
        name = "KK-Gewehr 100m (Scheibe Nr. 5)",
        ringDiametersMm = PRECISION_RINGS,
        innerTenDiameterMm = 25.0,
        blackDiameterMm = 200.0,
        defaultCaliberMm = 5.6,
        caliberName = ".22 lfB (5,6 mm)",
        distanceM = 100,
    )

    val ALL: List<TargetGeometry> = listOf(
        AIR_RIFLE_10M,
        AIR_PISTOL_10M,
        PRECISION_25M,
        SMALLBORE_RIFLE_50M,
        FREE_PISTOL_50M,
        SMALLBORE_RIFLE_100M,
    )

    fun bySlug(slug: String): TargetGeometry? = ALL.firstOrNull { it.slug == slug }

    /** What to pre-select when nothing else is known. */
    val DEFAULT: TargetGeometry = PRECISION_25M
}

/**
 * Bullet diameters for the caliber picker, mirroring
 * `app.core.target_type_seeds.CALIBERS`.
 *
 * Nominal BULLET diameters — what a caliber gauge measures against when a shot
 * sits on a ring line. Going from .22 to .45 moves every ring boundary on the
 * 25 m target outward by ~3 mm, about an eighth of a ring, so picking the right
 * one is not cosmetic.
 */
data class Caliber(val key: String, val name: String, val diameterMm: Double)

object Calibers {
    val ALL: List<Caliber> = listOf(
        Caliber("4.5", "4,5 mm Diabolo", 4.5),
        Caliber("5.6", ".22 lfB (5,6 mm)", 5.6),
        Caliber("7.62", "7,62 mm", 7.62),
        Caliber("9", "9 mm Luger", 9.0),
        Caliber("357", ".357 Magnum / .38 Special", 9.1),
        Caliber("44", ".44 Magnum", 10.9),
        Caliber("45", ".45 ACP", 11.5),
    )

    fun byDiameter(diameterMm: Double): Caliber? =
        ALL.firstOrNull { kotlin.math.abs(it.diameterMm - diameterMm) < 0.01 }
}
