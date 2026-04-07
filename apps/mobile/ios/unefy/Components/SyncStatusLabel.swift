import SwiftUI

/// Small footer showing when the list was last synced from the server.
/// Shown in grey below the list content.
struct SyncStatusLabel: View {
    let lastSyncedAt: Date?
    let fromCache: Bool

    var body: some View {
        HStack(spacing: 4) {
            Image(systemName: fromCache ? "cloud.slash" : "checkmark.circle")
            Text(statusText)
        }
        .font(.caption2)
        .foregroundStyle(.secondary)
    }

    private var statusText: String {
        guard let lastSyncedAt else {
            return String(localized: "sync.neverSynced")
        }
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .short
        let relative = formatter.localizedString(for: lastSyncedAt, relativeTo: .now)
        return String(format: String(localized: "sync.lastSynced"), relative)
    }
}
