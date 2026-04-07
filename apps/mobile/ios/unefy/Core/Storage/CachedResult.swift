import Foundation
import SwiftData

/// SwiftData cache for entries fetched from the API.
/// `eventId` field stores the session_id (reused name for migration simplicity).
@Model
final class CachedResult {
    @Attribute(.unique) var id: String
    var tenantId: String
    var eventId: String  // actually session_id
    var memberId: String
    var scoreValue: Double
    var scoreUnit: String
    var discipline: String?
    var detailsJSON: String?
    var source: String
    var recordedBy: String?
    var recordedAt: Date
    var notes: String?
    var cachedAt: Date

    init(from entry: Entry, tenantId: String, cachedAt: Date = .now) {
        self.id = entry.id
        self.tenantId = tenantId
        self.eventId = entry.sessionId
        self.memberId = entry.memberId
        self.scoreValue = entry.scoreValue
        self.scoreUnit = entry.scoreUnit
        self.discipline = entry.discipline
        if let details = entry.details, let data = try? JSONEncoder.snake.encode(details) {
            self.detailsJSON = String(data: data, encoding: .utf8)
        } else {
            self.detailsJSON = nil
        }
        self.source = entry.source
        self.recordedBy = entry.recordedBy
        self.recordedAt = entry.recordedAt
        self.notes = entry.notes
        self.cachedAt = cachedAt
    }

    func toEntry() -> Entry {
        var details: EntryDetails?
        if let json = detailsJSON, let data = json.data(using: .utf8) {
            details = try? JSONDecoder.apiDecoder.decode(EntryDetails.self, from: data)
        }
        return Entry(
            id: id,
            sessionId: eventId,
            memberId: memberId,
            scoreValue: scoreValue,
            scoreUnit: scoreUnit,
            discipline: discipline,
            details: details,
            source: source,
            recordedBy: recordedBy,
            recordedAt: recordedAt,
            notes: notes,
            createdAt: cachedAt,
            updatedAt: cachedAt
        )
    }
}
