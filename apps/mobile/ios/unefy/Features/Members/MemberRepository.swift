import Foundation

/// Result of a member list query. Tells the caller whether the data came
/// from the API or the local cache so the UI can show a freshness hint.
struct MemberListResult: Sendable {
    let members: [Member]
    let total: Int
    let hasMore: Bool
    let statusCounts: [String: Int]
    let fromCache: Bool
    let lastSyncedAt: Date?
}

/// Repository for member data. Read path is cache-aware, write path
/// (create/update/delete — to come later) goes straight to the API and
/// updates the cache on success.
@MainActor
final class MemberRepository {
    private let apiClient: APIClient
    private let localDB: LocalDatabase
    private let tenantId: String

    init(apiClient: APIClient, localDB: LocalDatabase, tenantId: String) {
        self.apiClient = apiClient
        self.localDB = localDB
        self.tenantId = tenantId
    }

    // MARK: - Read

    /// Primary list call. Tries the API first; falls back to cache on
    /// network failure. The API response is upserted into the cache as a
    /// side-effect so offline-reads see the latest data the user has
    /// seen.
    func list(
        page: Int,
        perPage: Int,
        search: String?,
        status: String?
    ) async throws -> MemberListResult {
        do {
            let response: ListResponse<Member> = try await apiClient.requestRaw(
                .members(page: page, perPage: perPage, search: search, status: status)
            )
            // Upsert page into cache (additive — don't delete anything).
            try? upsert(response.data)
            return MemberListResult(
                members: response.data,
                total: response.meta.total,
                hasMore: response.meta.page < response.meta.totalPages,
                statusCounts: response.meta.statusCounts ?? [:],
                fromCache: false,
                lastSyncedAt: nil
            )
        } catch APIError.network {
            return offlineList(search: search, status: status)
        } catch {
            throw error as? APIError ?? APIError.unauthorized
        }
    }

    /// Called on pull-to-refresh: fetches ALL pages and replaces the cache
    /// with the fresh snapshot. Stale members not in the snapshot are
    /// removed. Returns the first page for UI display.
    func fullSync(perPage: Int = 100) async throws -> MemberListResult {
        var all: [Member] = []
        var statusCounts: [String: Int] = [:]
        var page = 1

        while true {
            let response: ListResponse<Member> = try await apiClient.requestRaw(
                .members(page: page, perPage: perPage, search: nil, status: nil)
            )
            all.append(contentsOf: response.data)
            if statusCounts.isEmpty, let counts = response.meta.statusCounts {
                statusCounts = counts
            }
            if response.meta.page >= response.meta.totalPages || response.data.isEmpty {
                break
            }
            page += 1
            if page > 100 { break }  // safety cap — shouldn't happen in practice
        }

        try localDB.replaceMembers(all, tenantId: tenantId)
        let lastSynced = try? localDB.lastSyncedAt(tenantId: tenantId)

        return MemberListResult(
            members: Array(all.prefix(perPage)),
            total: all.count,
            hasMore: false,  // full sync returns everything already cached
            statusCounts: statusCounts,
            fromCache: false,
            lastSyncedAt: lastSynced
        )
    }

    func get(id: String) async throws -> Member {
        // Detail view — stay online-only for now. Offline support for
        // details can be added by reading from cache as a fallback once
        // we also cache individual lookups.
        try await apiClient.request(.member(id: id))
    }

    // MARK: - Offline fallback

    private func offlineList(search: String?, status: String?) -> MemberListResult {
        let cached = (try? localDB.cachedMembers(tenantId: tenantId)) ?? []
        let filtered = applyLocalFilter(cached, search: search, status: status)
        let counts = Dictionary(grouping: cached, by: { $0.status })
            .mapValues { $0.count }
        let lastSynced = try? localDB.lastSyncedAt(tenantId: tenantId)
        return MemberListResult(
            members: filtered,
            total: filtered.count,
            hasMore: false,
            statusCounts: counts,
            fromCache: true,
            lastSyncedAt: lastSynced
        )
    }

    private func applyLocalFilter(
        _ members: [Member],
        search: String?,
        status: String?
    ) -> [Member] {
        var result = members
        if let status, !status.isEmpty {
            result = result.filter { $0.status == status }
        }
        if let search, !search.isEmpty {
            let needle = search.lowercased()
            result = result.filter { member in
                member.firstName.lowercased().contains(needle)
                    || member.lastName.lowercased().contains(needle)
                    || member.memberNumber.lowercased().contains(needle)
                    || (member.email?.lowercased().contains(needle) ?? false)
            }
        }
        return result
    }

    // MARK: - Cache writes

    private func upsert(_ members: [Member]) throws {
        // Upsert-only (no deletes). Delete happens only via fullSync().
        // We piggyback on replaceMembers by merging with existing cache.
        let existing = (try? localDB.cachedMembers(tenantId: tenantId)) ?? []
        let existingByID = Dictionary(uniqueKeysWithValues: existing.map { ($0.id, $0) })
        var merged: [String: Member] = existingByID
        for member in members {
            merged[member.id] = member
        }
        try localDB.replaceMembers(Array(merged.values), tenantId: tenantId)
    }
}
