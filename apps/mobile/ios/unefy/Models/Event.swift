import Foundation

// MARK: - Competition

nonisolated struct Competition: Codable, Sendable, Identifiable, Equatable, Hashable {
    let id: String
    let name: String
    let description: String?
    let competitionType: String  // "league", "competition", "training"
    let startDate: String
    let endDate: String?
    let scoringMode: String  // "highest_wins", "lowest_wins"
    let scoringUnit: String  // "Ringe", "Punkte", "Sekunden"
    let disciplines: [String]?
    let createdAt: Date
    let updatedAt: Date

    var displayStartDate: String? { DateFormatting.displayDate(startDate) }
    var isLeague: Bool { competitionType == "league" }
    var isTraining: Bool { competitionType == "training" }
}

nonisolated struct CompetitionCreate: Codable, Sendable {
    let name: String
    let description: String?
    let competitionType: String
    let startDate: String
    let endDate: String?
    let scoringMode: String
    let scoringUnit: String
    let disciplines: [String]?
}

// MARK: - Session

nonisolated struct CompetitionSession: Codable, Sendable, Identifiable, Equatable, Hashable {
    let id: String
    let competitionId: String
    let name: String?
    let date: String
    let location: String?
    let discipline: String?
    let createdAt: Date
    let updatedAt: Date

    var displayDate: String? { DateFormatting.displayDate(date) }
}

nonisolated struct CompetitionSessionCreate: Codable, Sendable {
    let name: String?
    let date: String
    let location: String?
    let discipline: String?
}

// MARK: - Entry

nonisolated struct Entry: Codable, Sendable, Identifiable, Equatable, Hashable {
    let id: String
    let sessionId: String
    let memberId: String
    let scoreValue: Double
    let scoreUnit: String
    let discipline: String?
    let details: EntryDetails?
    let source: String
    let recordedBy: String?
    let recordedAt: Date
    let notes: String?
    let createdAt: Date
    let updatedAt: Date

    var isFromScan: Bool { source == "scan" }
}

/// Type-safe wrapper for the free-form `details` JSONB field.
/// Currently supports shooting data; other sports add properties here.
nonisolated struct EntryDetails: Codable, Sendable, Equatable, Hashable {
    let shots: [ShotDetail]?
    let targetType: String?

    // Future sports can add their fields here:
    // let splits: [String]?
    // let distanceM: Int?

    // Pass through unknown keys.
    struct ShotDetail: Codable, Sendable, Equatable, Hashable {
        let ring: Int
        let x: Double
        let y: Double
    }
}

nonisolated struct EntryCreatePayload: Codable, Sendable {
    let id: String?
    let memberId: String
    let scoreValue: Double
    let scoreUnit: String
    let discipline: String?
    let details: EntryDetails?
    let source: String
    let recordedAt: Date
    let notes: String?
}

// MARK: - Scoreboard

nonisolated struct ScoreboardRow: Codable, Sendable, Identifiable {
    let memberId: String
    let totalScore: Double
    let entryCount: Int
    let averageScore: Double
    let bestScore: Double
    let rank: Int

    var id: String { memberId }
}

nonisolated struct ScoreboardResponse: Codable, Sendable {
    let data: [ScoreboardRow]
    let scoringMode: String
    let scoringUnit: String
}
