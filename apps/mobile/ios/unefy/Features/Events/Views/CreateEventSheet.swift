import SwiftUI

// MARK: - Create Competition

struct CreateCompetitionSheet: View {
    var onCreated: (() async -> Void)?
    @Environment(AppState.self) private var appState
    @Environment(\.dismiss) private var dismiss

    @State private var name = ""
    @State private var competitionType = "competition"
    @State private var startDate = Date.now
    @State private var endDate = Date.now
    @State private var hasEndDate = false
    @State private var scoringUnit = "Ringe"
    @State private var scoringMode = "highest_wins"
    @State private var selectedDisciplines: [String] = []
    @State private var showDisciplinePicker = false
    @State private var pendingDiscipline = ""
    @State private var isLoading = false
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("events.name", text: $name)
                    Picker("events.type", selection: $competitionType) {
                        Text("Wettkampf").tag("competition")
                        Text("Liga").tag("league")
                        Text("Training").tag("training")
                    }
                    .onChange(of: competitionType) { _, newType in
                        if newType == "league" && !hasEndDate {
                            hasEndDate = true
                            endDate = Calendar.current.date(byAdding: .month, value: 6, to: startDate) ?? startDate
                        }
                    }
                    DatePicker(
                        hasEndDate ? "events.startDate" : "events.date",
                        selection: $startDate,
                        displayedComponents: .date
                    )
                    Toggle("events.hasEndDate", isOn: $hasEndDate)
                    if hasEndDate {
                        DatePicker("events.endDate", selection: $endDate, in: startDate..., displayedComponents: .date)
                    }
                }
                Section {
                    TextField("events.scoringUnit", text: $scoringUnit)
                    Picker("events.scoringMode", selection: $scoringMode) {
                        Text("events.highestWins").tag("highest_wins")
                        Text("events.lowestWins").tag("lowest_wins")
                    }
                }
                Section("events.disciplines") {
                    ForEach(selectedDisciplines, id: \.self) { disc in
                        HStack {
                            Text(disc)
                            Spacer()
                            Button {
                                selectedDisciplines.removeAll { $0 == disc }
                            } label: {
                                Image(systemName: "minus.circle.fill")
                                    .foregroundStyle(.red)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    Button {
                        showDisciplinePicker = true
                    } label: {
                        Label("events.addDiscipline", systemImage: "plus.circle")
                    }
                }
                if let error = errorMessage {
                    Section { Text(error).foregroundStyle(.red).font(.callout) }
                }
            }
            .navigationTitle("events.create")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("common.cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("common.save") { Task { await save() } }
                        .disabled(name.trimmingCharacters(in: .whitespaces).isEmpty || isLoading)
                }
            }
            .sheet(isPresented: $showDisciplinePicker) {
                DisciplinePickerView(selected: $pendingDiscipline)
                    .onChange(of: pendingDiscipline) { _, newValue in
                        if !newValue.isEmpty && !selectedDisciplines.contains(newValue) {
                            selectedDisciplines.append(newValue)
                        }
                        pendingDiscipline = ""
                    }
            }
        }
    }

    private func save() async {
        guard let context = appState.localDatabase?.context,
              let tenantId = appState.session?.tenant.id else { return }
        isLoading = true
        defer { isLoading = false }
        let fmt = DateFormatter(); fmt.dateFormat = "yyyy-MM-dd"

        let pending = PendingCompetition(
            name: name.trimmingCharacters(in: .whitespaces),
            competitionType: competitionType,
            startDate: fmt.string(from: startDate),
            endDate: hasEndDate ? fmt.string(from: endDate) : nil,
            scoringMode: scoringMode,
            scoringUnit: scoringUnit,
            disciplines: selectedDisciplines.isEmpty ? nil : selectedDisciplines,
            tenantId: tenantId
        )
        context.insert(pending)
        try? context.save()
        appState.syncEngine?.drainNow()
        dismiss()
        await onCreated?()
    }
}

// MARK: - Create Session

struct CreateSessionSheet: View {
    let competition: Competition
    var onCreated: (() async -> Void)?
    @Environment(AppState.self) private var appState
    @Environment(\.dismiss) private var dismiss

    @State private var name = ""
    @State private var date = Date.now
    @State private var location = ""
    @State private var discipline = ""
    @State private var isLoading = false
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("events.sessionName", text: $name)
                    DatePicker("events.date", selection: $date, displayedComponents: .date)
                    TextField("events.location", text: $location)
                    if let discs = competition.disciplines, !discs.isEmpty {
                        Picker("events.discipline", selection: $discipline) {
                            Text("–").tag("")
                            ForEach(discs, id: \.self) { Text($0).tag($0) }
                        }
                    } else {
                        TextField("events.discipline", text: $discipline)
                    }
                }
                if let error = errorMessage {
                    Section { Text(error).foregroundStyle(.red).font(.callout) }
                }
            }
            .navigationTitle("events.addSession")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("common.cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("common.save") { Task { await save() } }.disabled(isLoading)
                }
            }
        }
    }

    private func save() async {
        guard let context = appState.localDatabase?.context,
              let tenantId = appState.session?.tenant.id else { return }
        isLoading = true
        defer { isLoading = false }
        let fmt = DateFormatter(); fmt.dateFormat = "yyyy-MM-dd"

        let pending = PendingSession(
            competitionId: competition.id,
            name: name.isEmpty ? nil : name,
            date: fmt.string(from: date),
            location: location.isEmpty ? nil : location,
            discipline: discipline.isEmpty ? nil : discipline,
            tenantId: tenantId
        )
        context.insert(pending)
        try? context.save()
        appState.syncEngine?.drainNow()
        dismiss()
        await onCreated?()
    }
}
