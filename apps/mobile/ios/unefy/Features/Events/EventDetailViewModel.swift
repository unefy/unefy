import Foundation
import Observation
import SwiftData

/// Unified display row for an entry (synced or pending).
struct DisplayEntry: Identifiable, Equatable {
    enum SyncState: Equatable {
        case synced
        case pending
        case uploading
        case failed(String?)
    }

    let id: String
    let memberId: String
    let scoreValue: Double
    let scoreUnit: String
    let discipline: String?
    let details: EntryDetails?
    let source: String
    let recordedAt: Date
    let notes: String?
    let syncState: SyncState
}

@MainActor
@Observable
final class SessionDetailViewModel {
    enum LoadState: Equatable {
        case idle, loading, loaded, error(String)
    }

    let competition: Competition
    let session: CompetitionSession
    private(set) var displayEntries: [DisplayEntry] = []
    private(set) var state: LoadState = .idle

    private let repository: CompetitionRepository
    private let localDB: LocalDatabase?
    private let tenantId: String

    init(competition: Competition, session: CompetitionSession, apiClient: APIClient, localDB: LocalDatabase?, tenantId: String) {
        self.competition = competition
        self.session = session
        self.repository = CompetitionRepository(apiClient: apiClient)
        self.localDB = localDB
        self.tenantId = tenantId
    }

    func load() async {
        state = .loading
        try? localDB?.cleanUploadedPendingEntries(sessionId: session.id)

        var apiEntries: [Entry] = []
        do {
            let response = try await repository.entries(
                competitionId: competition.id, sessionId: session.id
            )
            apiEntries = response.data
            try? localDB?.cacheEntries(apiEntries, sessionId: session.id, tenantId: tenantId)
        } catch {
            apiEntries = (try? localDB?.cachedEntries(sessionId: session.id, tenantId: tenantId)) ?? []
        }

        let pending = loadPendingEntries()
        displayEntries = mergeEntries(apiEntries: apiEntries, pending: pending)
        state = .loaded
    }

    private func loadPendingEntries() -> [PendingEntry] {
        guard let context = localDB?.context else { return [] }
        let sessionId = session.id
        let descriptor = FetchDescriptor<PendingEntry>(
            predicate: #Predicate { $0.sessionId == sessionId && $0.syncStatusRaw != "uploaded" },
            sortBy: [SortDescriptor(\.createdAt)]
        )
        return (try? context.fetch(descriptor)) ?? []
    }

    private func mergeEntries(apiEntries: [Entry], pending: [PendingEntry]) -> [DisplayEntry] {
        let apiIDs = Set(apiEntries.map { $0.id })

        var merged: [DisplayEntry] = apiEntries.map { e in
            DisplayEntry(
                id: e.id, memberId: e.memberId, scoreValue: e.scoreValue,
                scoreUnit: e.scoreUnit, discipline: e.discipline, details: e.details,
                source: e.source, recordedAt: e.recordedAt, notes: e.notes, syncState: .synced
            )
        }

        for p in pending where !apiIDs.contains(p.clientId) {
            let syncState: DisplayEntry.SyncState = switch p.syncStatus {
            case .pending: .pending
            case .uploading: .uploading
            case .failed: .failed(p.failureReason)
            case .uploaded: .synced
            }
            merged.append(DisplayEntry(
                id: p.clientId, memberId: p.memberId, scoreValue: p.scoreValue,
                scoreUnit: p.scoreUnit, discipline: p.discipline, details: p.details,
                source: p.source, recordedAt: p.recordedAt, notes: p.notes, syncState: syncState
            ))
        }

        merged.sort { $0.recordedAt > $1.recordedAt }
        return merged
    }
}
