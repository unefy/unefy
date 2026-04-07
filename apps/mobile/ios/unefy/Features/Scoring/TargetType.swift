import Foundation

/// Defines the geometry of a shooting target per ISSF/DSB standards.
/// All measurements in millimeters.
///
/// `ringDiameters`: exactly 10 entries — index 0 = ring 10, index 9 = ring 1.
/// Each value is the OUTER diameter of that ring's scoring zone.
/// A hit scores ring N if any part of the bullet hole touches ring N's boundary.
nonisolated struct TargetType: Codable, Sendable, Identifiable, Hashable {
    let id: String
    let name: String
    /// Outer diameter of each ring in mm. Index 0 = ring 10, index 9 = ring 1.
    let ringDiameters: [Double]
    /// Mouche (inner ten / X-ring) diameter in mm. Used for tiebreakers.
    let moucheDiameter: Double
    /// Ring number from which the target is black (inclusive).
    let blackFromRing: Int
    /// Expected bullet hole diameter in mm.
    let caliberDiameter: Double
    /// Human-readable caliber name.
    let caliberName: String
    /// Distance in meters.
    let distance: Int

    var ringCount: Int { 10 }

    /// Total target diameter = ring 1 outer diameter.
    var totalDiameter: Double { ringDiameters.last ?? 500 }

    /// Fractional radius for a given ring (0...1 where 1 = target edge).
    func ringFraction(ring: Int) -> Double {
        guard ring >= 1, ring <= ringCount else { return 0 }
        let index = ring - 1  // ring 1 → index 0... no, ring 10 → index 0
        let idx = ringCount - ring  // ring 10 → 0, ring 1 → 9
        return (ringDiameters[idx] / 2.0) / (totalDiameter / 2.0)
    }

    /// Fractional radius of the Mouche.
    var moucheFraction: Double {
        (moucheDiameter / 2.0) / (totalDiameter / 2.0)
    }

    /// Calculate ring value for a hit at normalized distance from center
    /// (0 = dead center, 1 = outer edge of ring 1).
    func ringValue(normalizedDistance: Double) -> Int {
        let distanceMM = normalizedDistance * (totalDiameter / 2.0)
        // Bullet edge = closest point of bullet to center.
        let bulletEdgeMM = max(0, distanceMM - (caliberDiameter / 2.0))

        // Check from innermost (10) to outermost (1).
        for ring in stride(from: 10, through: 1, by: -1) {
            let idx = ringCount - ring  // ring 10→0, ring 9→1, ...
            let ringRadiusMM = ringDiameters[idx] / 2.0
            if bulletEdgeMM <= ringRadiusMM {
                return ring
            }
        }
        return 0  // outside ring 1
    }
}

// MARK: - Standard Target Types

extension TargetType {
    /// Sportpistole 25m (DSB Scheibe Nr. 5) — 9mm
    /// Ring width: 25mm. Black from ring 7.
    static let sportPistol25m = TargetType(
        id: "sport_pistol_25m",
        name: "Sportpistole 25m",
        ringDiameters: [50, 100, 150, 200, 250, 300, 350, 400, 450, 500],
        moucheDiameter: 25,
        blackFromRing: 7,
        caliberDiameter: 9.0,
        caliberName: "9mm",
        distance: 25
    )

    /// Luftpistole 10m (ISSF) — 4.5mm
    /// Ring width: 8mm. Black from ring 7.
    static let airPistol10m = TargetType(
        id: "air_pistol_10m",
        name: "Luftpistole 10m",
        ringDiameters: [11.5, 27.5, 43.5, 59.5, 75.5, 91.5, 107.5, 123.5, 139.5, 155.5],
        moucheDiameter: 5.0,
        blackFromRing: 7,
        caliberDiameter: 4.5,
        caliberName: "4.5mm",
        distance: 10
    )

    /// Luftgewehr 10m (ISSF) — 4.5mm
    /// Very small rings. Black from ring 4.
    static let airRifle10m = TargetType(
        id: "air_rifle_10m",
        name: "Luftgewehr 10m",
        ringDiameters: [5.0, 10.5, 16.0, 21.5, 27.0, 32.5, 38.0, 43.5, 49.0, 54.5],
        moucheDiameter: 0.5,
        blackFromRing: 4,
        caliberDiameter: 4.5,
        caliberName: "4.5mm",
        distance: 10
    )

    /// KK Gewehr 50m (ISSF) — 5.6mm (.22 LR)
    /// Black from ring 4.
    static let smallboreRifle50m = TargetType(
        id: "smallbore_rifle_50m",
        name: "KK Gewehr 50m",
        ringDiameters: [10.4, 26.4, 42.4, 58.4, 74.4, 90.4, 106.4, 122.4, 138.4, 154.4],
        moucheDiameter: 5.0,
        blackFromRing: 4,
        caliberDiameter: 5.6,
        caliberName: "5.6mm (.22 LR)",
        distance: 50
    )

    /// KK Gewehr 100m (DSB) — 5.6mm
    static let smallboreRifle100m = TargetType(
        id: "smallbore_rifle_100m",
        name: "KK Gewehr 100m",
        ringDiameters: [25, 75, 125, 175, 225, 275, 325, 375, 425, 500],
        moucheDiameter: 12.5,
        blackFromRing: 5,
        caliberDiameter: 5.6,
        caliberName: "5.6mm (.22 LR)",
        distance: 100
    )

    /// Freie Pistole 50m (ISSF) — 5.6mm
    static let freePistol50m = TargetType(
        id: "free_pistol_50m",
        name: "Freie Pistole 50m",
        ringDiameters: [25, 75, 125, 175, 225, 275, 325, 375, 425, 500],
        moucheDiameter: 12.5,
        blackFromRing: 7,
        caliberDiameter: 5.6,
        caliberName: "5.6mm (.22 LR)",
        distance: 50
    )

    static let allTypes: [TargetType] = [
        .sportPistol25m, .airPistol10m, .airRifle10m,
        .smallboreRifle50m, .smallboreRifle100m, .freePistol50m,
    ]

    static func byId(_ id: String) -> TargetType? {
        allTypes.first { $0.id == id }
    }
}
