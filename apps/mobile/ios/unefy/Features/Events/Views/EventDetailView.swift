import SwiftData
import SwiftUI

/// Shows sessions of a competition + scoreboard access.
/// For single-day competitions (no end_date), auto-creates a default session
/// and navigates directly to entries.
struct CompetitionDetailView: View {
    let competition: Competition
    @Environment(AppState.self) private var appState
    @State private var sessions: [CompetitionSession] = []
    @State private var isLoading = true
    @State private var showAddSession = false
    @State private var autoSession: CompetitionSession?
    @State private var sessionToDelete: CompetitionSession?
    @State private var navigateToAutoSession = false

    /// Single-day competition = no end date set.
    private var isSingleDay: Bool {
        competition.endDate == nil || competition.endDate == competition.startDate
    }

    var body: some View {
        Group {
            if isSingleDay, let session = autoSession {
                // Single-day: skip session list, show entries directly.
                SessionDetailView(competition: competition, session: session)
            } else {
                multiSessionView
            }
        }
        .task { await loadSessions() }
    }

    // MARK: - Multi-session view (leagues, multi-day)

    private var multiSessionView: some View {
        List {
            infoSection

            Section("events.sessions") {
                if isLoading {
                    ProgressView()
                } else if sessions.isEmpty {
                    Text("events.noSessions")
                        .foregroundStyle(.secondary)
                } else {
                    ForEach(sessions) { session in
                        NavigationLink(value: session) {
                            SessionRow(session: session)
                        }
                        .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                            Button(role: .destructive) {
                                sessionToDelete = session
                            } label: {
                                Label("common.delete", systemImage: "trash")
                            }
                        }
                    }
                }
            }

            Section {
                NavigationLink {
                    ScoreboardView(competition: competition)
                } label: {
                    Label("events.scoreboard", systemImage: "trophy")
                }
            }
        }
        .navigationTitle(competition.name)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button { showAddSession = true } label: {
                    Image(systemName: "plus")
                }
            }
        }
        .navigationDestination(for: CompetitionSession.self) { session in
            SessionDetailView(competition: competition, session: session)
        }
        .refreshable { await loadSessions() }
        .sheet(isPresented: $showAddSession) {
            CreateSessionSheet(competition: competition) { await loadSessions() }
        }
        .alert(
            "events.confirmDeleteSession",
            isPresented: .init(
                get: { sessionToDelete != nil },
                set: { if !$0 { sessionToDelete = nil } }
            )
        ) {
            Button("common.delete", role: .destructive) {
                if let s = sessionToDelete {
                    Task {
                        try? await appState.apiClient.requestVoid(
                            .deleteSession(competitionId: competition.id, sessionId: s.id)
                        )
                        await loadSessions()
                    }
                }
            }
            Button("common.cancel", role: .cancel) {}
        }
    }

    private var infoSection: some View {
        Section {
            if let start = competition.displayStartDate {
                if let endDate = competition.endDate,
                   let end = DateFormatting.displayDate(endDate),
                   endDate != competition.startDate {
                    LabeledContent("events.startDate", value: start)
                    LabeledContent("events.endDate", value: end)
                } else {
                    LabeledContent("events.date", value: start)
                }
            }
            LabeledContent("events.type") {
                Text(competition.competitionType)
            }
            LabeledContent("events.scoringUnit", value: competition.scoringUnit)
            if let disciplines = competition.disciplines, !disciplines.isEmpty {
                LabeledContent("events.discipline") {
                    Text(disciplines.joined(separator: ", "))
                }
            }
        }
    }

    // MARK: - Loading

    private func loadSessions() async {
        let repo = CompetitionRepository(apiClient: appState.apiClient)
        do {
            let response = try await repo.sessions(competitionId: competition.id)
            var merged = response.data
            let pending = loadPendingSessions()
            let apiIDs = Set(merged.map { $0.id })
            for p in pending where !apiIDs.contains(p.clientId) {
                merged.insert(p.toSession(), at: 0)
            }
            sessions = merged
        } catch {
            sessions = loadPendingSessions().map { $0.toSession() }
        }
        isLoading = false

        // Single-day: ensure a default session exists.
        if isSingleDay {
            if let first = sessions.first {
                autoSession = first
            } else {
                await createDefaultSession()
            }
        }
    }

    /// Create a default session for single-day competitions.
    private func createDefaultSession() async {
        guard let context = appState.localDatabase?.context,
              let tenantId = appState.session?.tenant.id else { return }

        let pending = PendingSession(
            competitionId: competition.id,
            name: nil,
            date: competition.startDate,
            location: nil,
            discipline: competition.disciplines?.first,
            tenantId: tenantId
        )
        context.insert(pending)
        try? context.save()
        appState.syncEngine?.drainNow()
        autoSession = pending.toSession()
    }

    private func loadPendingSessions() -> [PendingSession] {
        guard let context = appState.localDatabase?.context else { return [] }
        let compId = competition.id
        let descriptor = FetchDescriptor<PendingSession>(
            predicate: #Predicate { $0.competitionId == compId && $0.syncStatusRaw != "uploaded" },
            sortBy: [SortDescriptor(\.createdAt)]
        )
        return (try? context.fetch(descriptor)) ?? []
    }
}

private struct SessionRow: View {
    let session: CompetitionSession
    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(session.name ?? session.displayDate ?? session.date)
                .font(.body)
            HStack(spacing: 6) {
                if let discipline = session.discipline {
                    Text(discipline)
                }
                if let location = session.location {
                    Text("·")
                    Text(location)
                }
            }
            .font(.caption)
            .foregroundStyle(.secondary)
        }
    }
}
