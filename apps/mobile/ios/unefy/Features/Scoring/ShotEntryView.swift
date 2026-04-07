import SwiftUI

/// Full-screen shot entry: interactive target + editable shot list.
struct ShotEntryView: View {
    let competition: Competition
    let session: CompetitionSession
    var onSaved: (() async -> Void)?

    @Environment(AppState.self) private var appState
    @Environment(\.dismiss) private var dismiss

    @State private var shots: [PlacedShot] = []
    @State private var selectedMember: Member?
    @State private var targetType: TargetType = .sportPistol25m
    @State private var members: [Member] = []
    @State private var isLoadingMembers = true
    @State private var isSaving = false
    @State private var showSettings = false
    @State private var editingShot: PlacedShot?

    private var totalScore: Int { shots.map(\.ring).reduce(0, +) }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                scoreHeader
                    .padding(.horizontal)
                    .padding(.top, 8)

                // Interactive target — top half
                InteractiveTargetView(
                    targetType: targetType,
                    shots: $shots,
                    onLongPressShot: { shot in
                        editingShot = shot
                    }
                )
                .frame(maxHeight: .infinity)
                .padding(.horizontal, 4)

                // Shot list + controls — bottom half
                shotListAndControls
            }
            .navigationTitle("scoring.title")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("common.cancel") { dismiss() }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button { showSettings = true } label: {
                        Image(systemName: "gearshape")
                    }
                }
            }
            .sheet(isPresented: $showSettings) { settingsSheet }
            .sheet(item: $editingShot) { shot in
                editShotSheet(shot: shot)
            }
            .task { await loadMembers() }
            .onAppear { inferTargetType() }
        }
    }

    // MARK: - Score Header

    private var scoreHeader: some View {
        HStack(alignment: .firstTextBaseline) {
            Text("\(totalScore)")
                .font(.system(size: 32, weight: .bold, design: .rounded))
                .monospacedDigit()
            Text("\(shots.count) \(String(localized: "scoring.shots"))")
                .font(.callout)
                .foregroundStyle(.secondary)
            Spacer()
            Text(targetType.name)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }

    // MARK: - Shot List + Controls

    private var shotListAndControls: some View {
        VStack(spacing: 0) {
            if !shots.isEmpty {
                shotList
            }
            bottomControls
        }
        .background(.ultraThinMaterial)
    }

    private var shotList: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 6) {
                ForEach(shots) { shot in
                    shotChip(shot: shot)
                }
            }
            .padding(.horizontal)
            .padding(.vertical, 8)
        }
    }

    private func shotChip(shot: PlacedShot) -> some View {
        Button {
            editingShot = shot
        } label: {
            Text("\(shot.ring)")
                .font(.system(size: 16, weight: .bold, design: .rounded))
                .monospacedDigit()
                .frame(width: 36, height: 36)
                .background(ringColor(shot.ring).opacity(0.2), in: Circle())
                .foregroundStyle(ringColor(shot.ring))
                .overlay(
                    Circle().strokeBorder(ringColor(shot.ring).opacity(0.4), lineWidth: 1)
                )
        }
        .buttonStyle(.plain)
    }

    private var bottomControls: some View {
        VStack(spacing: 10) {
            // Member picker
            Picker("events.member", selection: $selectedMember) {
                Text("events.selectMemberPrompt").tag(nil as Member?)
                ForEach(members) { m in
                    Text("\(m.fullName)").tag(m as Member?)
                }
            }
            .pickerStyle(.menu)
            .disabled(isLoadingMembers)

            HStack(spacing: 12) {
                Button {
                    guard !shots.isEmpty else { return }
                    withAnimation { _ = shots.removeLast() }
                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
                } label: {
                    Label("scoring.undo", systemImage: "arrow.uturn.backward")
                }
                .buttonStyle(.bordered)
                .disabled(shots.isEmpty)

                Button {
                    Task { await save() }
                } label: {
                    Label("common.save", systemImage: "checkmark.circle")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .disabled(selectedMember == nil || shots.isEmpty || isSaving)
            }
        }
        .padding(.horizontal)
        .padding(.vertical, 10)
    }

    // MARK: - Edit Shot Sheet

    private func editShotSheet(shot: PlacedShot) -> some View {
        NavigationStack {
            Form {
                Section {
                    HStack {
                        Text("scoring.ringValue")
                        Spacer()
                        Picker("", selection: Binding(
                            get: {
                                shots.first { $0.id == shot.id }?.ring ?? shot.ring
                            },
                            set: { newRing in
                                if let idx = shots.firstIndex(where: { $0.id == shot.id }) {
                                    shots[idx].ring = newRing
                                }
                            }
                        )) {
                            ForEach((0...10).reversed(), id: \.self) { ring in
                                Text("\(ring)").tag(ring)
                            }
                        }
                        .pickerStyle(.wheel)
                        .frame(width: 100, height: 120)
                    }
                }

                Section {
                    Button("scoring.deleteShot", role: .destructive) {
                        withAnimation { shots.removeAll { $0.id == shot.id } }
                        editingShot = nil
                        UIImpactFeedbackGenerator(style: .medium).impactOccurred()
                    }
                }
            }
            .navigationTitle("scoring.editShot")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("common.save") { editingShot = nil }
                }
            }
        }
        .presentationDetents([.height(300)])
    }

    // MARK: - Settings Sheet

    private var settingsSheet: some View {
        NavigationStack {
            Form {
                Picker("scanner.targetType", selection: $targetType) {
                    ForEach(TargetType.allTypes) { tt in
                        Text(tt.name).tag(tt)
                    }
                }
                Section {
                    Button("scoring.clearAll", role: .destructive) {
                        withAnimation { shots.removeAll() }
                        showSettings = false
                    }
                    .disabled(shots.isEmpty)
                }
            }
            .navigationTitle("scoring.settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("common.save") { showSettings = false }
                }
            }
        }
        .presentationDetents([.medium])
    }

    // MARK: - Logic

    private func inferTargetType() {
        let disc = session.discipline ?? competition.disciplines?.first ?? ""
        if let match = TargetType.allTypes.first(where: {
            disc.lowercased().contains($0.id.replacingOccurrences(of: "_", with: " "))
        }) {
            targetType = match
        }
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

        let shotDetails = shots.map {
            EntryDetails.ShotDetail(ring: $0.ring, x: $0.x, y: $0.y)
        }
        let details = EntryDetails(shots: shotDetails, targetType: targetType.id)

        let pending = PendingEntry(
            competitionId: competition.id,
            sessionId: session.id,
            memberId: member.id,
            scoreValue: Double(totalScore),
            scoreUnit: competition.scoringUnit,
            discipline: session.discipline ?? competition.disciplines?.first,
            details: details,
            source: "manual",
            tenantId: tenantId
        )
        context.insert(pending)
        try? context.save()
        appState.syncEngine?.activeEventName = competition.name
        appState.syncEngine?.drainNow()
        dismiss()
        await onSaved?()
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
