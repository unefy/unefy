import ActivityKit
import Foundation

/// Manages the Live Activity lifecycle for sync status.
/// Nonisolated because ActivityKit APIs are thread-safe.
nonisolated final class SyncActivityManager: @unchecked Sendable {
    private let lock = NSLock()
    private var activityId: String?
    private var _uploadedCount: Int = 0

    var uploadedCount: Int {
        lock.lock()
        defer { lock.unlock() }
        return _uploadedCount
    }

    func update(pendingCount: Int, isOnline: Bool, eventName: String?) {
        let shouldBeActive = pendingCount > 0 || !isOnline

        if shouldBeActive {
            let state = SyncActivityAttributes.ContentState(
                pendingCount: pendingCount,
                isOnline: isOnline,
                uploadedCount: uploadedCount
            )

            if activityId != nil {
                updateActivity(state: state)
            } else {
                startActivity(state: state, eventName: eventName ?? "unefy")
            }
        } else {
            endActivity()
        }
    }

    func trackUpload() {
        lock.lock()
        _uploadedCount += 1
        lock.unlock()
    }

    func reset() {
        lock.lock()
        _uploadedCount = 0
        lock.unlock()
        endActivity()
    }

    private func startActivity(
        state: SyncActivityAttributes.ContentState,
        eventName: String
    ) {
        guard ActivityAuthorizationInfo().areActivitiesEnabled else { return }

        let attributes = SyncActivityAttributes(eventName: eventName)
        let content = ActivityContent(state: state, staleDate: nil)

        do {
            let activity = try Activity.request(
                attributes: attributes,
                content: content,
                pushType: nil
            )
            lock.lock()
            activityId = activity.id
            lock.unlock()
        } catch {
            // Live Activities not available.
        }
    }

    private func updateActivity(state: SyncActivityAttributes.ContentState) {
        lock.lock()
        let id = activityId
        lock.unlock()
        guard let id else { return }

        let activity = Activity<SyncActivityAttributes>.activities.first { $0.id == id }
        guard let activity else {
            lock.lock()
            activityId = nil
            lock.unlock()
            return
        }
        let content = ActivityContent(state: state, staleDate: nil)
        Task {
            await activity.update(content)
        }
    }

    private func endActivity() {
        lock.lock()
        let id = activityId
        let uploaded = _uploadedCount
        activityId = nil
        _uploadedCount = 0
        lock.unlock()

        guard let id else { return }
        let activity = Activity<SyncActivityAttributes>.activities.first { $0.id == id }
        guard let activity else { return }

        let finalState = SyncActivityAttributes.ContentState(
            pendingCount: 0,
            isOnline: true,
            uploadedCount: uploaded
        )
        let content = ActivityContent(state: finalState, staleDate: nil)
        Task {
            await activity.end(content, dismissalPolicy: .after(.now + 5))
        }
    }
}
