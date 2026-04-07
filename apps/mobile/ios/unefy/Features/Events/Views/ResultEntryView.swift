import SwiftUI

struct EntryFormView: View {
    let competition: Competition
    let session: CompetitionSession
    var onSaved: (() async -> Void)?

    @Environment(AppState.self) private var appState
    @Environment(\.dismiss) private var dismiss

    @State private var selectedMember: Member?
    @State private var discipline: String = ""
    @State private var scoreText: String = ""
    @State private var shotInputs: [String] = Array(repeating: "", count: 10)
    @State private var showShotGrid = false
    @State private var isSaving = false
    @State private var errorMessage: String?
    @State private var members: [Member] = []
    @State private var isLoadingMembers = true

    private var isShooting: Bool {
        let unit = competition.scoringUnit.lowercased()
        return unit.contains("ring") || unit.contains("punkt")
    }

    var body: some View {
        NavigationStack {
            Form {
                memberSection
                disciplineSection

                if isShooting {
                    shootingShotsSection
                } else {
                    genericScoreSection
                }

                summarySection

                if let error = errorMessage {
                    Section { Text(error).foregroundStyle(.red).font(.callout) }
                }
            }
            .navigationTitle("events.addResult")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("common.cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("common.save") { Task { await save() } }.disabled(!canSave)
                }
            }
            .task { await loadMembers() }
            .onAppear {
                discipline = session.discipline ?? competition.disciplines?.first ?? ""
            }
        }
    }

    // MARK: - Sections

    private var memberSection: some View {
        Section("events.selectMember") {
            if isLoadingMembers {
                ProgressView()
            } else {
                Picker("events.member", selection: $selectedMember) {
                    Text("events.selectMemberPrompt").tag(nil as Member?)
                    ForEach(members) { member in
                        Text("\(member.fullName) (#\(member.memberNumber))").tag(member as Member?)
                    }
                }
                .pickerStyle(.navigationLink)
            }
        }
    }

    private var disciplineSection: some View {
        Section {
            if let discs = competition.disciplines, !discs.isEmpty {
                Picker("events.discipline", selection: $discipline) {
                    ForEach(discs, id: \.self) { Text($0).tag($0) }
                }
            } else {
                TextField("events.discipline", text: $discipline)
            }
        }
    }

    private var shootingShotsSection: some View {
        Section("events.shots") {
            LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 8), count: 5), spacing: 8) {
                ForEach(0..<shotInputs.count, id: \.self) { index in
                    TextField("\(index + 1)", text: $shotInputs[index])
                        .keyboardType(.numberPad)
                        .multilineTextAlignment(.center)
                        .frame(height: 44)
                        .background(Color(.secondarySystemGroupedBackground))
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                }
            }
            HStack {
                Button("events.addShot") { shotInputs.append("") }
                Spacer()
                if shotInputs.count > 1 {
                    Button("events.removeShot", role: .destructive) { shotInputs.removeLast() }
                }
            }
            .font(.caption)
        }
    }

    private var genericScoreSection: some View {
        Section {
            HStack {
                TextField("events.scoreValue", text: $scoreText)
                    .keyboardType(.decimalPad)
                Text(competition.scoringUnit)
                    .foregroundStyle(.secondary)
            }
        }
    }

    private var summarySection: some View {
        Section {
            LabeledContent("events.totalScore") {
                Text(String(format: "%.0f", computedScore))
                    .font(.title2).fontWeight(.bold).monospacedDigit()
            }
        }
    }

    // MARK: - Logic

    private var parsedShots: [Int] {
        shotInputs.compactMap { Int($0.trimmingCharacters(in: .whitespaces)) }.filter { (0...10).contains($0) }
    }

    private var computedScore: Double {
        isShooting ? Double(parsedShots.reduce(0, +)) : (Double(scoreText) ?? 0)
    }

    private var canSave: Bool {
        !isSaving && selectedMember != nil && computedScore > 0
    }

    private func loadMembers() async {
        guard let tenantId = appState.session?.tenant.id, let localDB = appState.localDatabase else {
            isLoadingMembers = false; return
        }
        let cached = (try? localDB.cachedMembers(tenantId: tenantId)) ?? []
        if !cached.isEmpty { members = cached; isLoadingMembers = false; return }
        do {
            let repo = MemberRepository(apiClient: appState.apiClient, localDB: localDB, tenantId: tenantId)
            let result = try await repo.fullSync()
            members = result.members
        } catch { members = cached }
        isLoadingMembers = false
    }

    private func save() async {
        guard let member = selectedMember, let context = appState.localDatabase?.context,
              let tenantId = appState.session?.tenant.id else { return }
        isSaving = true; errorMessage = nil
        defer { isSaving = false }

        var details: EntryDetails? = nil
        if isShooting && !parsedShots.isEmpty {
            // For manual entry, distribute shots evenly around center with slight random offset.
            let shotDetails = parsedShots.map { ring in
                let distance = Double(10 - ring) / 10.0
                let angle = Double.random(in: 0..<(.pi * 2))
                return EntryDetails.ShotDetail(
                    ring: ring,
                    x: distance * cos(angle) * 0.9,
                    y: distance * sin(angle) * 0.9
                )
            }
            details = EntryDetails(shots: shotDetails, targetType: discipline.isEmpty ? nil : discipline)
        }

        let pending = PendingEntry(
            competitionId: competition.id, sessionId: session.id,
            memberId: member.id, scoreValue: computedScore,
            scoreUnit: competition.scoringUnit, discipline: discipline.isEmpty ? nil : discipline,
            details: details, source: "manual", tenantId: tenantId
        )
        context.insert(pending)
        try? context.save()
        appState.syncEngine?.activeEventName = competition.name
        appState.syncEngine?.drainNow()
        dismiss()
        await onSaved?()
    }
}
