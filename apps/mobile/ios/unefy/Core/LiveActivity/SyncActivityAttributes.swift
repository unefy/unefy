import ActivityKit
import Foundation

/// Defines the data model for the sync status Live Activity.
/// Shown on Dynamic Island (background) and Lock Screen.
nonisolated struct SyncActivityAttributes: ActivityAttributes {
    nonisolated struct ContentState: Codable, Hashable {
        /// Number of results waiting to be uploaded.
        var pendingCount: Int
        /// Whether the device is currently online.
        var isOnline: Bool
        /// Total results uploaded in this session.
        var uploadedCount: Int
    }

    /// Name of the event being synced (static, set at start).
    var eventName: String
}
