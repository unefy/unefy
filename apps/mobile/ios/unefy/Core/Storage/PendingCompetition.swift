import Foundation
import SwiftData

/// A competition queued for creation. Synced before sessions and entries.
@Model
final class PendingCompetition {
    enum SyncStatus: String, Codable {
        case pending, uploading, uploaded, failed
    }

    @Attribute(.unique) var clientId: String
    var tenantId: String
    var name: String
    var competitionType: String
    var startDate: String
    var endDate: String?
    var scoringMode: String
    var scoringUnit: String
    var disciplinesJSON: String?

    var syncStatusRaw: String
    var failureReason: String?
    var createdAt: Date

    init(
        name: String, competitionType: String, startDate: String, endDate: String?,
        scoringMode: String, scoringUnit: String, disciplines: [String]?,
        tenantId: String
    ) {
        self.clientId = UUID().uuidString
        self.tenantId = tenantId
        self.name = name
        self.competitionType = competitionType
        self.startDate = startDate
        self.endDate = endDate
        self.scoringMode = scoringMode
        self.scoringUnit = scoringUnit
        if let d = disciplines, let data = try? JSONEncoder().encode(d) {
            self.disciplinesJSON = String(data: data, encoding: .utf8)
        }
        self.syncStatusRaw = SyncStatus.pending.rawValue
        self.createdAt = .now
    }

    var syncStatus: SyncStatus {
        get { SyncStatus(rawValue: syncStatusRaw) ?? .pending }
        set { syncStatusRaw = newValue.rawValue }
    }

    var disciplines: [String]? {
        guard let json = disciplinesJSON, let data = json.data(using: .utf8) else { return nil }
        return try? JSONDecoder().decode([String].self, from: data)
    }

    func toPayload() -> CompetitionCreate {
        CompetitionCreate(
            name: name, description: nil, competitionType: competitionType,
            startDate: startDate, endDate: endDate,
            scoringMode: scoringMode, scoringUnit: scoringUnit,
            disciplines: disciplines
        )
    }

    /// Produces a local Competition object for immediate display.
    func toCompetition() -> Competition {
        Competition(
            id: clientId, name: name, description: nil,
            competitionType: competitionType, startDate: startDate,
            endDate: endDate, scoringMode: scoringMode, scoringUnit: scoringUnit,
            disciplines: disciplines, createdAt: createdAt, updatedAt: createdAt
        )
    }
}
