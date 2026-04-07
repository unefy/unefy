import ActivityKit
import SwiftUI
import WidgetKit

struct SyncLiveActivity: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: SyncActivityAttributes.self) { context in
            // LOCK SCREEN / banner presentation
            lockScreenView(context: context)
        } dynamicIsland: { context in
            DynamicIsland {
                // EXPANDED — shown when user long-presses the Dynamic Island
                DynamicIslandExpandedRegion(.leading) {
                    Image(systemName: context.state.isOnline ? "arrow.up.circle" : "wifi.slash")
                        .font(.title2)
                        .foregroundStyle(context.state.isOnline ? .blue : .orange)
                }
                DynamicIslandExpandedRegion(.trailing) {
                    VStack(alignment: .trailing) {
                        Text("\(context.state.pendingCount)")
                            .font(.title)
                            .fontWeight(.bold)
                            .monospacedDigit()
                        Text("ausstehend")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                }
                DynamicIslandExpandedRegion(.center) {
                    VStack(spacing: 2) {
                        Text(context.attributes.eventName)
                            .font(.headline)
                            .lineLimit(1)
                        if context.state.uploadedCount > 0 {
                            Text("\(context.state.uploadedCount) hochgeladen")
                                .font(.caption)
                                .foregroundStyle(.green)
                        }
                    }
                }
                DynamicIslandExpandedRegion(.bottom) {
                    if !context.state.isOnline {
                        Text("Offline — wird synchronisiert sobald Netz verfügbar")
                            .font(.caption2)
                            .foregroundStyle(.orange)
                            .multilineTextAlignment(.center)
                    } else if context.state.pendingCount > 0 {
                        ProgressView()
                            .controlSize(.small)
                            .tint(.blue)
                    }
                }
            } compactLeading: {
                // COMPACT — left side of Dynamic Island pill
                Image(systemName: context.state.isOnline ? "arrow.up.circle.fill" : "wifi.slash")
                    .foregroundStyle(context.state.isOnline ? .blue : .orange)
            } compactTrailing: {
                // COMPACT — right side of Dynamic Island pill
                Text("\(context.state.pendingCount)")
                    .font(.caption)
                    .fontWeight(.bold)
                    .monospacedDigit()
                    .foregroundStyle(context.state.pendingCount > 0 ? Color.primary : Color.green)
            } minimal: {
                // MINIMAL — when other Live Activities compete for space
                Image(systemName: context.state.pendingCount > 0 ? "arrow.up.circle.fill" : "checkmark.circle.fill")
                    .foregroundStyle(context.state.pendingCount > 0 ? Color.orange : Color.green)
            }
        }
    }

    @ViewBuilder
    private func lockScreenView(context: ActivityViewContext<SyncActivityAttributes>) -> some View {
        HStack(spacing: 12) {
            // Status icon
            Image(systemName: context.state.isOnline ? "arrow.up.circle.fill" : "wifi.slash")
                .font(.title2)
                .foregroundStyle(context.state.isOnline ? .blue : .orange)

            VStack(alignment: .leading, spacing: 2) {
                Text(context.attributes.eventName)
                    .font(.headline)
                    .lineLimit(1)
                Group {
                    if !context.state.isOnline {
                        Text("Offline · \(context.state.pendingCount) ausstehend")
                            .foregroundStyle(.orange)
                    } else if context.state.pendingCount > 0 {
                        Text("\(context.state.pendingCount) wird hochgeladen…")
                            .foregroundStyle(.blue)
                    } else {
                        Text("Alles synchronisiert ✓")
                            .foregroundStyle(.green)
                    }
                }
                .font(.subheadline)
            }

            Spacer()

            if context.state.uploadedCount > 0 {
                VStack {
                    Text("\(context.state.uploadedCount)")
                        .font(.title2)
                        .fontWeight(.bold)
                        .monospacedDigit()
                    Text("sync'd")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .padding()
    }
}
