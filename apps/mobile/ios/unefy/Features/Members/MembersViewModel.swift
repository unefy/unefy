import Foundation
import Observation

@MainActor
@Observable
final class MembersViewModel {
    enum LoadState: Equatable {
        case idle
        case loading
        case loaded
        case error(String)
    }

    private(set) var members: [Member] = []
    private(set) var state: LoadState = .idle
    private(set) var isLoadingMore: Bool = false
    private(set) var total: Int = 0
    private(set) var availableStatusCounts: [String: Int] = [:]
    private(set) var showingCachedData: Bool = false
    private(set) var lastSyncedAt: Date?

    var searchText: String = "" {
        didSet { onSearchTextChanged() }
    }

    var statusFilter: String? {
        didSet {
            guard oldValue != statusFilter else { return }
            Task { await refresh() }
        }
    }

    private let repository: MemberRepository
    private let perPage: Int = 20
    private var page: Int = 1
    private var hasMore: Bool = true
    private var searchTask: Task<Void, Never>?

    init(repository: MemberRepository) {
        self.repository = repository
    }

    func loadInitial() async {
        guard members.isEmpty, state == .idle else { return }
        await refresh()
    }

    /// Pull-to-refresh: tries a full sync of all members into the cache.
    /// Falls back to a paginated API list if full sync fails, or the
    /// cache if the device is offline.
    func refresh() async {
        searchTask?.cancel()
        page = 1
        hasMore = true
        state = .loading

        // Try full sync first — best for offline-readiness.
        // Only do this if there's no active search/filter (otherwise the
        // sync would be misleading; user expects filtered view).
        if trimmedSearch == nil && statusFilter == nil {
            do {
                let result = try await repository.fullSync()
                applyResult(result)
                return
            } catch APIError.network {
                // Fall through to offline-aware list() below.
            } catch let error as APIError {
                state = .error(ErrorMessageMapper.message(for: error))
                return
            } catch {
                // Unexpected — try offline read.
            }
        }

        // Filtered query or full-sync fallback.
        do {
            let result = try await repository.list(
                page: page,
                perPage: perPage,
                search: trimmedSearch,
                status: statusFilter
            )
            applyResult(result)
        } catch let error as APIError {
            state = .error(ErrorMessageMapper.message(for: error))
        } catch {
            state = .error(String(localized: "errors.unknown"))
        }
    }

    func loadMoreIfNeeded(currentItem: Member) async {
        guard hasMore, !isLoadingMore, state == .loaded, !showingCachedData else { return }
        guard currentItem == members.last else { return }

        isLoadingMore = true
        defer { isLoadingMore = false }

        let nextPage = page + 1
        do {
            let result = try await repository.list(
                page: nextPage,
                perPage: perPage,
                search: trimmedSearch,
                status: statusFilter
            )
            members.append(contentsOf: result.members)
            page = nextPage
            hasMore = result.hasMore
        } catch {
            // Non-fatal — user can try scrolling again
        }
    }

    // MARK: - Helpers

    private func applyResult(_ result: MemberListResult) {
        members = result.members
        total = result.total
        hasMore = result.hasMore
        showingCachedData = result.fromCache
        lastSyncedAt = result.lastSyncedAt
        if statusFilter == nil {
            availableStatusCounts = result.statusCounts
        }
        state = .loaded
    }

    private var trimmedSearch: String? {
        let trimmed = searchText.trimmingCharacters(in: .whitespaces)
        return trimmed.isEmpty ? nil : trimmed
    }

    private func onSearchTextChanged() {
        searchTask?.cancel()
        searchTask = Task { [weak self] in
            try? await Task.sleep(for: .milliseconds(300))
            if Task.isCancelled { return }
            await self?.refresh()
        }
    }
}
