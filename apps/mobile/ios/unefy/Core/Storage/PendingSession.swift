import Foundation
import SwiftData

/// A session queued for creation. Synced after competitions, before entries.
@Model
final class PendingSession {
    enum SyncStatus: String, Codable {
        case pending, uploading, uploaded, failed
    }

    @Attribute(.unique) var clientId: String
    var tenantId: String
    var competitionId: String  // may be a PendingCompetition.clientId
    var name: String?
    var date: String
    var location: String?
    var discipline: String?

    var syncStatusRaw: String
    var failureReason: String?
    var createdAt: Date

    init(
        competitionId: String, name: String?, date: String,
        location: String?, discipline: String?, tenantId: String
    ) {
        self.clientId = UUID().uuidString
        self.tenantId = tenantId
        self.competitionId = competitionId
        self.name = name
        self.date = date
        self.location = location
        self.discipline = discipline
        self.syncStatusRaw = SyncStatus.pending.rawValue
        self.createdAt = .now
    }

    var syncStatus: SyncStatus {
        get { SyncStatus(rawValue: syncStatusRaw) ?? .pending }
        set { syncStatusRaw = newValue.rawValue }
    }

    func toPayload() -> CompetitionSessionCreate {
        CompetitionSessionCreate(name: name, date: date, location: location, discipline: discipline)
    }

    func toSession() -> CompetitionSession {
        CompetitionSession(
            id: clientId, competitionId: competitionId, name: name,
            date: date, location: location, discipline: discipline,
            createdAt: createdAt, updatedAt: createdAt
        )
    }
}
