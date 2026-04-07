import SwiftUI

/// Shows the scanned image with detected hits overlaid. User can confirm,
/// remove, or add hits. On save → creates an Entry with shot coordinates.
struct ScanReviewView: View {
    let image: UIImage
    let scanResult: ScanResult
    let competition: Competition
    let session: CompetitionSession
    var onSaved: (() async -> Void)?

    @Environment(AppState.self) private var appState
    @State private var confirmedHits: [Detection]
    @State private var clusterCounts: [String: Int] = [:]
    @State private var selectedMember: Member?
    @State private var members: [Member] = []
    @State private var isLoadingMembers = true
    @State private var isSaving = false
    @State private var targetType: TargetType?

    init(image: UIImage, scanResult: ScanResult, competition: Competition,
         session: CompetitionSession, onSaved: (() async -> Void)?) {
        self.image = image
        self.scanResult = scanResult
        self.competition = competition
        self.session = session
        self.onSaved = onSaved
        // Pre-populate with detected hits (excluding patches).
        _confirmedHits = State(initialValue: scanResult.hits + scanResult.clusters)
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                // Annotated image
                annotatedImage
                    .frame(maxHeight: 400)

                statsSection
                memberSection
                targetTypeSection

                if !confirmedHits.isEmpty {
                    hitsListSection
                }

                saveButton
            }
            .padding()
        }
        .navigationTitle("scanner.review")
        .navigationBarTitleDisplayMode(.inline)
        .task { await loadMembers() }
    }

    // MARK: - Annotated Image

    private var annotatedImage: some View {
        GeometryReader { geo in
            let imageSize = image.size
            let scale = min(geo.size.width / imageSize.width, geo.size.height / imageSize.height)
            let displayW = imageSize.width * scale
            let displayH = imageSize.height * scale
            let offsetX = (geo.size.width - displayW) / 2
            let offsetY = (geo.size.height - displayH) / 2

            ZStack(alignment: .topLeading) {
                Image(uiImage: image)
                    .resizable()
                    .scaledToFit()

                // Draw detection boxes.
                ForEach(scanResult.detections) { det in
                    let rect = CGRect(
                        x: offsetX + det.bbox.origin.x * displayW,
                        y: offsetY + det.bbox.origin.y * displayH,
                        width: det.bbox.width * displayW,
                        height: det.bbox.height * displayH
                    )

                    Rectangle()
                        .strokeBorder(colorFor(det), lineWidth: det.isTarget ? 2 : 1.5)
                        .frame(width: rect.width, height: rect.height)
                        .overlay(alignment: .topLeading) {
                            Text(labelFor(det))
                                .font(.system(size: 8, weight: .bold))
                                .padding(2)
                                .background(colorFor(det).opacity(0.8))
                                .foregroundStyle(.white)
                        }
                        .position(x: rect.midX, y: rect.midY)
                        .opacity(det.isPatch ? 0.4 : 1)
                }
            }
        }
        .aspectRatio(image.size, contentMode: .fit)
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    // MARK: - Sections

    private var statsSection: some View {
        HStack(spacing: 24) {
            StatBadge(label: "scanner.hitsFound", value: "\(confirmedHits.count)", color: .green)
            StatBadge(label: "scanner.patchesIgnored", value: "\(scanResult.patches.count)", color: .gray)
            StatBadge(
                label: "scanner.totalScore",
                value: "\(computedScore)",
                color: .blue
            )
        }
    }

    private var memberSection: some View {
        Section {
            if isLoadingMembers {
                ProgressView()
            } else {
                Picker("events.member", selection: $selectedMember) {
                    Text("events.selectMemberPrompt").tag(nil as Member?)
                    ForEach(members) { m in
                        Text("\(m.fullName) (#\(m.memberNumber))").tag(m as Member?)
                    }
                }
            }
        }
    }

    private var targetTypeSection: some View {
        Picker("scanner.targetType", selection: $targetType) {
            Text("–").tag(nil as TargetType?)
            ForEach(TargetType.allTypes) { tt in
                Text(tt.name).tag(tt as TargetType?)
            }
        }
        .onAppear {
            // Try to infer from competition discipline.
            if let disc = session.discipline ?? competition.disciplines?.first {
                targetType = TargetType.allTypes.first {
                    disc.lowercased().contains($0.name.lowercased())
                    || disc.lowercased().contains($0.id.replacingOccurrences(of: "_", with: " "))
                }
            }
        }
    }

    private var hitsListSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("scanner.detectedHits")
                .font(.headline)

            ForEach(Array(confirmedHits.enumerated()), id: \.element.id) { index, hit in
                HStack {
                    Text("\(index + 1).")
                        .font(.caption)
                        .frame(width: 24)
                    Text(hit.className)
                        .font(.caption)
                    Spacer()
                    if let pos = scanResult.normalizedPosition(of: hit), let tt = targetType {
                        let dist = sqrt(pos.x * pos.x + pos.y * pos.y)
                        let ring = tt.ringValue(normalizedDistance: dist)
                        Text("Ring \(ring)")
                            .font(.caption)
                            .fontWeight(.bold)
                    }
                    Text("\(Int(hit.confidence * 100))%")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                    Button {
                        confirmedHits.remove(at: index)
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundStyle(.red)
                    }
                    .buttonStyle(.plain)
                }
            }
        }
        .padding()
        .background(Color(.secondarySystemGroupedBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private var saveButton: some View {
        Button {
            Task { await save() }
        } label: {
            if isSaving {
                ProgressView()
                    .frame(maxWidth: .infinity)
            } else {
                Label("scanner.saveResult", systemImage: "checkmark.circle")
                    .frame(maxWidth: .infinity)
            }
        }
        .buttonStyle(.borderedProminent)
        .controlSize(.large)
        .disabled(selectedMember == nil || confirmedHits.isEmpty || isSaving)
    }

    // MARK: - Logic

    private var computedScore: Int {
        guard let tt = targetType else { return 0 }
        return confirmedHits.compactMap { hit -> Int? in
            guard let pos = scanResult.normalizedPosition(of: hit) else { return nil }
            let dist = sqrt(pos.x * pos.x + pos.y * pos.y)
            return tt.ringValue(normalizedDistance: dist)
        }.reduce(0, +)
    }

    private func loadMembers() async {
        guard let tenantId = appState.session?.tenant.id,
              let localDB = appState.localDatabase else {
            isLoadingMembers = false; return
        }
        members = (try? localDB.cachedMembers(tenantId: tenantId)) ?? []
        isLoadingMembers = false
    }

    private func save() async {
        guard let member = selectedMember,
              let context = appState.localDatabase?.context,
              let tenantId = appState.session?.tenant.id else { return }
        isSaving = true
        defer { isSaving = false }

        let tt = targetType
        let shotDetails: [EntryDetails.ShotDetail] = confirmedHits.compactMap { hit in
            guard let pos = scanResult.normalizedPosition(of: hit) else { return nil }
            let dist = sqrt(pos.x * pos.x + pos.y * pos.y)
            let ring = tt?.ringValue(normalizedDistance: dist) ?? 0
            return EntryDetails.ShotDetail(ring: ring, x: pos.x, y: pos.y)
        }

        let details = EntryDetails(
            shots: shotDetails,
            targetType: tt?.id
        )
        let totalScore = Double(shotDetails.map(\.ring).reduce(0, +))

        let pending = PendingEntry(
            competitionId: competition.id,
            sessionId: session.id,
            memberId: member.id,
            scoreValue: totalScore,
            scoreUnit: competition.scoringUnit,
            discipline: session.discipline ?? competition.disciplines?.first,
            details: details,
            source: "scan",
            tenantId: tenantId
        )
        context.insert(pending)
        try? context.save()
        appState.syncEngine?.activeEventName = competition.name
        appState.syncEngine?.drainNow()
        await onSaved?()
    }

    // MARK: - Helpers

    private func colorFor(_ det: Detection) -> Color {
        if det.isTarget { return .green }
        if det.isTargetCenter { return .blue }
        if det.isPatch { return .gray }
        if det.isCluster { return .orange }
        return .red  // hits
    }

    private func labelFor(_ det: Detection) -> String {
        if det.isTarget { return "Scheibe" }
        if det.isTargetCenter { return "Mitte" }
        if det.isPatch { return "Pflaster" }
        if det.isCluster { return "Cluster" }
        return "\(det.className) \(Int(det.confidence * 100))%"
    }
}

private struct StatBadge: View {
    let label: LocalizedStringKey
    let value: String
    let color: Color

    var body: some View {
        VStack(spacing: 4) {
            Text(value)
                .font(.title2)
                .fontWeight(.bold)
                .monospacedDigit()
            Text(label)
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 8)
        .background(color.opacity(0.1), in: RoundedRectangle(cornerRadius: 8))
    }
}
