import SwiftUI

/// Compact pill-shaped status indicator that sits just below the Dynamic
/// Island / notch area. Shows offline state or pending upload count.
struct GlobalSyncBanner: View {
    @Environment(AppState.self) private var appState

    var body: some View {
        let isOnline = appState.networkMonitor.isOnline
        let pendingCount = appState.syncEngine?.pendingCount ?? 0
        let isVisible = !isOnline || pendingCount > 0

        if isVisible {
            HStack(spacing: 6) {
                if !isOnline {
                    Image(systemName: "wifi.slash")
                        .font(.caption2)
                    Text("Offline")
                        .font(.caption2)
                        .fontWeight(.semibold)
                } else if pendingCount > 0 {
                    ProgressView()
                        .controlSize(.mini)
                    Text("\(pendingCount)")
                        .font(.caption2)
                        .fontWeight(.semibold)
                    Image(systemName: "arrow.up")
                        .font(.caption2)
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 5)
            .background(.ultraThinMaterial, in: .capsule)
            .overlay(
                Capsule()
                    .strokeBorder(
                        isOnline ? .blue.opacity(0.3) : .orange.opacity(0.3),
                        lineWidth: 0.5
                    )
            )
            .foregroundStyle(isOnline ? .blue : .orange)
            .transition(.opacity.combined(with: .scale(scale: 0.8)))
            .animation(.spring(duration: 0.3), value: isOnline)
            .animation(.spring(duration: 0.3), value: pendingCount)
        }
    }
}
