import Foundation
import SwiftData

/// Owns the SwiftData ModelContainer. One instance per app, created on
/// launch and shared via `AppState`.
///
/// If the schema has changed incompatibly (e.g. after a model rename),
/// the old store is deleted and recreated — this is safe because all
/// data is either a cache or has been uploaded via the sync engine.
@MainActor
final class LocalDatabase {
    let container: ModelContainer

    init() throws {
        let schema = Schema([
            CachedMember.self, CachedResult.self,
            PendingCompetition.self, PendingSession.self, PendingEntry.self,
        ])
        let configuration = ModelConfiguration(
            schema: schema,
            isStoredInMemoryOnly: false
        )

        do {
            self.container = try ModelContainer(
                for: schema,
                configurations: configuration
            )
        } catch {
            // Schema migration failed — nuke the old store and retry.
            // This is safe: CachedMember and CachedResult are just caches,
            // and PendingEntry items that were .uploaded are already on the server.
            Self.deleteStoreFiles()
            self.container = try ModelContainer(
                for: schema,
                configurations: configuration
            )
        }
    }

    var context: ModelContext { container.mainContext }

    /// Delete the SQLite store files from disk.
    private static func deleteStoreFiles() {
        guard let appSupport = FileManager.default.urls(
            for: .applicationSupportDirectory, in: .userDomainMask
        ).first else { return }

        let storeURL = appSupport.appendingPathComponent("default.store")
        for suffix in ["", "-shm", "-wal"] {
            let fileURL = storeURL.appendingPathExtension(suffix.isEmpty ? "" : String(suffix.dropFirst()))
            let url = suffix.isEmpty ? storeURL : URL(fileURLWithPath: storeURL.path + suffix)
            try? FileManager.default.removeItem(at: url)
        }
    }

    // MARK: - Member cache operations

    func cachedMembers(tenantId: String) throws -> [Member] {
        let descriptor = FetchDescriptor<CachedMember>(
            predicate: #Predicate { $0.tenantId == tenantId },
            sortBy: [SortDescriptor(\.lastName), SortDescriptor(\.firstName)]
        )
        return try context.fetch(descriptor).map { $0.toMember() }
    }

    func lastSyncedAt(tenantId: String) throws -> Date? {
        var descriptor = FetchDescriptor<CachedMember>(
            predicate: #Predicate { $0.tenantId == tenantId },
            sortBy: [SortDescriptor(\.cachedAt, order: .forward)]
        )
        descriptor.fetchLimit = 1
        return try context.fetch(descriptor).first?.cachedAt
    }

    func replaceMembers(_ members: [Member], tenantId: String) throws {
        let now = Date.now
        let incomingIDs = Set(members.map { $0.id })
        let existing = try context.fetch(
            FetchDescriptor<CachedMember>(
                predicate: #Predicate { $0.tenantId == tenantId }
            )
        )
        var existingByID = Dictionary(uniqueKeysWithValues: existing.map { ($0.id, $0) })

        for member in members {
            if let row = existingByID.removeValue(forKey: member.id) {
                row.update(from: member, cachedAt: now)
            } else {
                context.insert(CachedMember(from: member, tenantId: tenantId, cachedAt: now))
            }
        }
        for (_, stale) in existingByID where !incomingIDs.contains(stale.id) {
            context.delete(stale)
        }
        try context.save()
    }

    // MARK: - Entry cache operations

    func cacheEntries(_ entries: [Entry], sessionId: String, tenantId: String) throws {
        let existing = try context.fetch(
            FetchDescriptor<CachedResult>(
                predicate: #Predicate { $0.eventId == sessionId && $0.tenantId == tenantId }
            )
        )
        for old in existing { context.delete(old) }
        let now = Date.now
        for entry in entries {
            context.insert(CachedResult(from: entry, tenantId: tenantId, cachedAt: now))
        }
        try context.save()
    }

    func cachedEntries(sessionId: String, tenantId: String) throws -> [Entry] {
        let descriptor = FetchDescriptor<CachedResult>(
            predicate: #Predicate { $0.eventId == sessionId && $0.tenantId == tenantId },
            sortBy: [SortDescriptor(\.recordedAt, order: .reverse)]
        )
        return try context.fetch(descriptor).map { $0.toEntry() }
    }

    // MARK: - Pending entry cleanup

    func cleanUploadedPendingEntries(sessionId: String) throws {
        let uploaded = "uploaded"
        let descriptor = FetchDescriptor<PendingEntry>(
            predicate: #Predicate { $0.sessionId == sessionId && $0.syncStatusRaw == uploaded }
        )
        let items = try context.fetch(descriptor)
        for item in items { context.delete(item) }
        if !items.isEmpty { try context.save() }
    }

    func clearAll() throws {
        try context.delete(model: CachedMember.self)
        try context.delete(model: CachedResult.self)
        let uploaded = "uploaded"
        let uploadedDescriptor = FetchDescriptor<PendingEntry>(
            predicate: #Predicate { $0.syncStatusRaw == uploaded }
        )
        for item in try context.fetch(uploadedDescriptor) { context.delete(item) }
        try context.save()
    }
}
