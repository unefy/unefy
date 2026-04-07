import SwiftUI

/// Detail view for a single entry. Shows interactive target (editable),
/// score breakdown, and meta info. Changes save directly.
struct EntryDetailView: View {
    let entry: DisplayEntry
    let competition: Competition
    let session: CompetitionSession
    var onChanged: (() async -> Void)?

    @Environment(AppState.self) private var appState
    @State private var shots: [PlacedShot] = []
    @State private var hasChanges = false
    @State private var isSaving = false

    private var targetType: TargetType {
        entry.details?.targetType.flatMap { TargetType.byId($0) } ?? .sportPistol25m
    }

    private var totalScore: Int { shots.map(\.ring).reduce(0, +) }

    @State private var bottomExpanded = false

    var body: some View {
        GeometryReader { geo in
            let bottomHeight: CGFloat = bottomExpanded ? geo.size.height * 0.45 : 56
            let targetHeight = geo.size.height - 60 - bottomHeight

            VStack(spacing: 0) {
                // Score header
                scoreHeader
                    .frame(height: 60)

                // Target — fills available space
                InteractiveTargetView(
                    targetType: targetType,
                    shots: $shots
                )
                .frame(height: max(targetHeight, 200))
                .onChange(of: shots) { _, _ in
                    hasChanges = true
                }

                // Bottom drawer — tap to expand/collapse
                VStack(spacing: 0) {
                    // Handle
                    Button {
                        withAnimation(.spring(duration: 0.3)) {
                            bottomExpanded.toggle()
                        }
                    } label: {
                        VStack(spacing: 4) {
                            Capsule()
                                .fill(.secondary.opacity(0.4))
                                .frame(width: 36, height: 4)
                            if !shots.isEmpty && !bottomExpanded {
                                // Compact: show chips inline
                                ScrollView(.horizontal, showsIndicators: false) {
                                    HStack(spacing: 4) {
                                        ForEach(shots) { shot in
                                            Text("\(shot.ring)")
                                                .font(.system(size: 12, weight: .bold, design: .rounded))
                                                .frame(width: 26, height: 26)
                                                .background(ringColor(shot.ring).opacity(0.2), in: Circle())
                                                .foregroundStyle(ringColor(shot.ring))
                                        }
                                    }
                                    .padding(.horizontal)
                                }
                            }
                        }
                        .padding(.top, 8)
                        .padding(.bottom, 4)
                    }
                    .buttonStyle(.plain)

                    if bottomExpanded {
                        ScrollView {
                            VStack(spacing: 16) {
                                if !shots.isEmpty {
                                    shotChips
                                    shotBreakdown
                                }
                                metaSection
                            }
                            .padding(.bottom, 16)
                        }
                    }
                }
                .background(.ultraThinMaterial)
            }
        }
        .navigationTitle(entry.discipline ?? competition.scoringUnit)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            if hasChanges {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        Task { await save() }
                    } label: {
                        Text("common.save")
                            .fontWeight(.semibold)
                    }
                    .disabled(isSaving)
                }
            }
        }
        .onAppear { loadShots() }
    }

    // MARK: - Score Header

    private var scoreHeader: some View {
        VStack(spacing: 2) {
            Text("\(totalScore)")
                .font(.system(size: 44, weight: .bold, design: .rounded))
                .monospacedDigit()
            HStack(spacing: 6) {
                Text(competition.scoringUnit)
                Text("·")
                Text("\(shots.count) \(String(localized: "events.shotsLabel"))")
            }
            .font(.subheadline)
            .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
    }

    // MARK: - Shot Chips

    private var shotChips: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 6) {
                ForEach(shots) { shot in
                    Text("\(shot.ring)")
                        .font(.system(size: 14, weight: .bold, design: .rounded))
                        .frame(width: 32, height: 32)
                        .background(ringColor(shot.ring).opacity(0.2), in: Circle())
                        .foregroundStyle(ringColor(shot.ring))
                }
            }
            .padding(.horizontal)
        }
    }

    // MARK: - Shot Breakdown

    private var shotBreakdown: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("scoring.shotValues")
                .font(.headline)
                .padding(.horizontal)

            let ringCounts = Dictionary(grouping: shots, by: { $0.ring })
                .mapValues { $0.count }
                .sorted { $0.key > $1.key }

            LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 6), count: 6), spacing: 6) {
                ForEach(ringCounts, id: \.key) { ring, count in
                    VStack(spacing: 2) {
                        Text("\(ring)")
                            .font(.system(size: 18, weight: .bold, design: .rounded))
                            .monospacedDigit()
                        Text("×\(count)")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 8)
                    .background(ringColor(ring).opacity(0.15), in: RoundedRectangle(cornerRadius: 8))
                }
            }
            .padding(.horizontal)
        }
    }

    // MARK: - Meta

    private var metaSection: some View {
        VStack(spacing: 0) {
            Divider().padding(.horizontal)
            Group {
                if let discipline = entry.discipline {
                    infoRow("events.discipline", value: discipline)
                }
                infoRow("scoring.source", value: entry.source == "scan" ? String(localized: "events.sourceAI") : String(localized: "scoring.manualSource"))
                infoRow("scoring.recordedAt", value: entry.recordedAt.formatted(date: .abbreviated, time: .shortened))
            }
            .padding(.horizontal)
        }
    }

    private func infoRow(_ label: LocalizedStringKey, value: String) -> some View {
        HStack {
            Text(label)
                .foregroundStyle(.secondary)
            Spacer()
            Text(value)
        }
        .font(.callout)
        .padding(.vertical, 6)
    }

    // MARK: - Logic

    private func loadShots() {
        guard let shotDetails = entry.details?.shots else { return }
        shots = shotDetails.map { detail in
            var shot = PlacedShot(x: detail.x, y: detail.y)
            shot.ring = detail.ring
            return shot
        }
        hasChanges = false
    }

    private func save() async {
        guard let context = appState.localDatabase?.context,
              let tenantId = appState.session?.tenant.id else { return }
        isSaving = true
        defer { isSaving = false }

        let shotDetails = shots.map {
            EntryDetails.ShotDetail(ring: $0.ring, x: $0.x, y: $0.y)
        }
        let details = EntryDetails(shots: shotDetails, targetType: targetType.id)

        let pending = PendingEntry(
            competitionId: competition.id,
            sessionId: session.id,
            memberId: entry.memberId,
            scoreValue: Double(totalScore),
            scoreUnit: competition.scoringUnit,
            discipline: entry.discipline,
            details: details,
            source: entry.source,
            tenantId: tenantId
        )
        context.insert(pending)
        try? context.save()
        appState.syncEngine?.drainNow()
        hasChanges = false
        await onChanged?()
    }

    private func ringColor(_ ring: Int) -> Color {
        switch ring {
        case 10: .yellow
        case 9: .green
        case 8: .blue
        case 7: .cyan
        default: .secondary
        }
    }
}
