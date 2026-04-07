import Foundation
import SwiftData

/// A scoring entry queued for upload. Created offline (or online),
/// persisted in SwiftData, drained by `ResultSyncEngine` when network
/// is available.
///
/// The `clientId` is sent as the entry's `id` to the backend —
/// idempotent creates ensure no duplicates on retry.
@Model
final class PendingEntry {
    enum SyncStatus: String, Codable {
        case pending
        case uploading
        case uploaded
        case failed
    }

    @Attribute(.unique) var clientId: String
    var tenantId: String
    var competitionId: String
    var sessionId: String
    var memberId: String
    var scoreValue: Double
    var scoreUnit: String
    var discipline: String?
    /// JSON-encoded sport-specific details.
    var detailsJSON: String?
    var source: String
    var recordedAt: Date
    var notes: String?

    var syncStatusRaw: String
    var failureReason: String?
    var lastAttemptAt: Date?
    var attemptCount: Int
    var createdAt: Date

    init(
        competitionId: String,
        sessionId: String,
        memberId: String,
        scoreValue: Double,
        scoreUnit: String,
        discipline: String? = nil,
        details: EntryDetails? = nil,
        source: String = "manual",
        recordedAt: Date = .now,
        notes: String? = nil,
        tenantId: String
    ) {
        self.clientId = UUID().uuidString
        self.tenantId = tenantId
        self.competitionId = competitionId
        self.sessionId = sessionId
        self.memberId = memberId
        self.scoreValue = scoreValue
        self.scoreUnit = scoreUnit
        self.discipline = discipline
        if let details, let data = try? JSONEncoder.snake.encode(details) {
            self.detailsJSON = String(data: data, encoding: .utf8)
        } else {
            self.detailsJSON = nil
        }
        self.source = source
        self.recordedAt = recordedAt
        self.notes = notes
        self.syncStatusRaw = SyncStatus.pending.rawValue
        self.attemptCount = 0
        self.createdAt = .now
    }

    var syncStatus: SyncStatus {
        get { SyncStatus(rawValue: syncStatusRaw) ?? .pending }
        set { syncStatusRaw = newValue.rawValue }
    }

    var details: EntryDetails? {
        guard let json = detailsJSON, let data = json.data(using: .utf8) else { return nil }
        return try? JSONDecoder.apiDecoder.decode(EntryDetails.self, from: data)
    }

    func toPayload() -> EntryCreatePayload {
        EntryCreatePayload(
            id: clientId,
            memberId: memberId,
            scoreValue: scoreValue,
            scoreUnit: scoreUnit,
            discipline: discipline,
            details: details,
            source: source,
            recordedAt: recordedAt,
            notes: notes
        )
    }
}
