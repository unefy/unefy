import Foundation
import Observation
import SwiftData

extension Notification.Name {
    static let resultsSynced = Notification.Name("de.unefy.resultsSynced")
}

/// Drains the PendingEntry queue when the device is online.
/// Each result is uploaded via its client-generated UUID — idempotent,
/// safe to retry.
///
/// Reacts to two triggers:
/// 1. Network state change (offline → online) → immediate drain
/// 2. Periodic poll every 30s as fallback
/// 3. Manual `drainNow()` after entering a new result
@MainActor
@Observable
final class ResultSyncEngine {
    private let apiClient: APIClient
    private let context: ModelContext
    private let networkMonitor: NetworkMonitor
    private let activityManager = SyncActivityManager()
    private var pollTask: Task<Void, Never>?
    private var observeTask: Task<Void, Never>?
    private var isDraining = false

    /// Number of results still pending upload. Observable by the UI.
    private(set) var pendingCount: Int = 0

    /// Name of the event currently being synced (for Live Activity display).
    var activeEventName: String?

    init(apiClient: APIClient, context: ModelContext, networkMonitor: NetworkMonitor) {
        self.apiClient = apiClient
        self.context = context
        self.networkMonitor = networkMonitor
    }

    func start() {
        refreshPendingCount()

        // Immediate drain on start.
        drainNow()

        // React to network state changes → drain immediately when going online.
        observeTask = Task { [weak self] in
            var wasOnline = self?.networkMonitor.isOnline ?? true
            while !Task.isCancelled {
                // withObservationTracking fires once per change.
                let isOnline = await withCheckedContinuation { continuation in
                    withObservationTracking {
                        _ = self?.networkMonitor.isOnline
                    } onChange: {
                        Task { @MainActor in
                            continuation.resume(returning: self?.networkMonitor.isOnline ?? false)
                        }
                    }
                }
                if Task.isCancelled { break }
                // Always update Live Activity on network change.
                self?.updateLiveActivity()
                // Transition: offline → online → drain.
                if !wasOnline && isOnline {
                    await self?.drain()
                }
                wasOnline = isOnline
            }
        }

        // Fallback: periodic poll every 30s.
        pollTask = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(30))
                if Task.isCancelled { break }
                if self?.pendingCount ?? 0 > 0, self?.networkMonitor.isOnline == true {
                    await self?.drain()
                }
            }
        }
    }

    func stop() {
        pollTask?.cancel()
        pollTask = nil
        observeTask?.cancel()
        observeTask = nil
    }

    /// Manually trigger a drain (e.g. after entering a new result).
    func drainNow() {
        refreshPendingCount()
        Task { await drain() }
    }

    func refreshPendingCount() {
        let compCount = (try? context.fetchCount(FetchDescriptor<PendingCompetition>(
            predicate: #Predicate { $0.syncStatusRaw == "pending" || $0.syncStatusRaw == "failed" }
        ))) ?? 0
        let sessCount = (try? context.fetchCount(FetchDescriptor<PendingSession>(
            predicate: #Predicate { $0.syncStatusRaw == "pending" || $0.syncStatusRaw == "failed" }
        ))) ?? 0
        let entryCount = (try? context.fetchCount(FetchDescriptor<PendingEntry>(
            predicate: #Predicate { $0.syncStatusRaw == "pending" || $0.syncStatusRaw == "failed" }
        ))) ?? 0
        pendingCount = compCount + sessCount + entryCount
        updateLiveActivity()
    }

    private func updateLiveActivity() {
        activityManager.update(
            pendingCount: pendingCount,
            isOnline: networkMonitor.isOnline,
            eventName: activeEventName
        )
    }

    // MARK: - Drain loop (ordered: competitions → sessions → entries)

    private func drain() async {
        guard !isDraining else { return }
        guard networkMonitor.isOnline else { return }
        isDraining = true
        defer {
            isDraining = false
            refreshPendingCount()
            NotificationCenter.default.post(name: .resultsSynced, object: nil)
        }

        // Phase 1: Competitions
        await drainCompetitions()
        // Phase 2: Sessions (depend on competitions existing)
        await drainSessions()
        // Phase 3: Entries (depend on sessions existing)
        await drainEntries()
    }

    private func drainCompetitions() async {
        let descriptor = FetchDescriptor<PendingCompetition>(
            predicate: #Predicate { $0.syncStatusRaw == "pending" || $0.syncStatusRaw == "failed" },
            sortBy: [SortDescriptor(\.createdAt)]
        )
        guard let items = try? context.fetch(descriptor) else { return }
        for item in items {
            if !networkMonitor.isOnline { break }
            item.syncStatus = .uploading
            do {
                let payload = item.toPayload()
                let _: Competition = try await apiClient.request(
                    .createCompetition(payload, clientId: item.clientId)
                )
                item.syncStatus = .uploaded
                try? context.save()
                activityManager.trackUpload()
            } catch {
                item.syncStatus = .failed
                item.failureReason = "\(error)"
                try? context.save()
            }
        }
    }

    private func drainSessions() async {
        let descriptor = FetchDescriptor<PendingSession>(
            predicate: #Predicate { $0.syncStatusRaw == "pending" || $0.syncStatusRaw == "failed" },
            sortBy: [SortDescriptor(\.createdAt)]
        )
        guard let items = try? context.fetch(descriptor) else { return }
        for item in items {
            if !networkMonitor.isOnline { break }
            item.syncStatus = .uploading
            do {
                let payload = item.toPayload()
                let _: CompetitionSession = try await apiClient.request(
                    .createSession(
                        competitionId: item.competitionId,
                        data: payload,
                        clientId: item.clientId
                    )
                )
                item.syncStatus = .uploaded
                try? context.save()
                activityManager.trackUpload()
            } catch {
                item.syncStatus = .failed
                item.failureReason = "\(error)"
                try? context.save()
            }
        }
    }

    private func drainEntries() async {
        let descriptor = FetchDescriptor<PendingEntry>(
            predicate: #Predicate { $0.syncStatusRaw == "pending" || $0.syncStatusRaw == "failed" },
            sortBy: [SortDescriptor(\.createdAt)]
        )
        guard let items = try? context.fetch(descriptor) else { return }
        for item in items {
            if Task.isCancelled { break }
            if !networkMonitor.isOnline { break }
            await uploadEntry(item)
        }
    }

    private func uploadEntry(_ item: PendingEntry) async {
        item.syncStatus = .uploading
        item.lastAttemptAt = .now
        item.attemptCount += 1

        do {
            let _: Entry = try await apiClient.request(
                .createEntry(
                    competitionId: item.competitionId,
                    sessionId: item.sessionId,
                    payload: item.toPayload()
                )
            )
            item.syncStatus = .uploaded
            try? context.save()
            activityManager.trackUpload()
        } catch let error as APIError {
            switch error {
            case .server(let status, _, let message) where (400..<500).contains(status):
                item.syncStatus = .failed
                item.failureReason = "HTTP \(status): \(message)"
            default:
                item.syncStatus = .failed
                item.failureReason = "Retryable: \(error.code)"
            }
            try? context.save()
        } catch {
            item.syncStatus = .failed
            item.failureReason = error.localizedDescription
            try? context.save()
        }
    }
}
