import Foundation
import Observation
import SwiftData

@MainActor
@Observable
final class CompetitionsViewModel {
    enum LoadState: Equatable {
        case idle, loading, loaded, error(String)
    }

    private(set) var competitions: [Competition] = []
    private(set) var state: LoadState = .idle

    private let repository: CompetitionRepository
    private let context: ModelContext?

    init(apiClient: APIClient, context: ModelContext?) {
        self.repository = CompetitionRepository(apiClient: apiClient)
        self.context = context
    }

    func loadInitial() async {
        guard competitions.isEmpty, state == .idle else { return }
        await refresh()
    }

    func refresh() async {
        state = .loading
        do {
            let response = try await repository.list(page: 1, perPage: 100)
            var merged = response.data
            // Add pending (not yet uploaded) competitions.
            let pending = loadPendingCompetitions()
            let apiIDs = Set(merged.map { $0.id })
            for p in pending where !apiIDs.contains(p.clientId) {
                merged.insert(p.toCompetition(), at: 0)
            }
            competitions = merged
            state = .loaded
        } catch let error as APIError {
            // Offline: show pending competitions only.
            competitions = loadPendingCompetitions().map { $0.toCompetition() }
            state = competitions.isEmpty
                ? .error(ErrorMessageMapper.message(for: error))
                : .loaded
        } catch {
            state = .error(String(localized: "errors.unknown"))
        }
    }

    private func loadPendingCompetitions() -> [PendingCompetition] {
        guard let context else { return [] }
        let descriptor = FetchDescriptor<PendingCompetition>(
            predicate: #Predicate { $0.syncStatusRaw != "uploaded" },
            sortBy: [SortDescriptor(\.createdAt, order: .reverse)]
        )
        return (try? context.fetch(descriptor)) ?? []
    }
}
