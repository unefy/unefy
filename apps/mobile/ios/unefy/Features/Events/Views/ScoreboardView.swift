import SwiftUI

struct ScoreboardView: View {
    let competition: Competition
    @Environment(AppState.self) private var appState
    @State private var rows: [ScoreboardRow] = []
    @State private var isLoading = true
    @State private var scoringUnit = ""
    @State private var members: [String: Member] = [:]

    var body: some View {
        List {
            if isLoading {
                ProgressView()
            } else if rows.isEmpty {
                Text("events.noResults")
                    .foregroundStyle(.secondary)
            } else {
                ForEach(rows) { row in
                    HStack {
                        Text("#\(row.rank)")
                            .font(.title3)
                            .fontWeight(.bold)
                            .monospacedDigit()
                            .frame(width: 40, alignment: .leading)
                            .foregroundStyle(row.rank <= 3 ? .orange : .secondary)

                        VStack(alignment: .leading, spacing: 2) {
                            Text(memberName(row.memberId))
                                .font(.body)
                                .fontWeight(.medium)
                            Text("\(row.entryCount) Ergebnisse · Ø \(String(format: "%.1f", row.averageScore)) · Best \(String(format: "%.0f", row.bestScore))")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }

                        Spacer()

                        Text(String(format: "%.0f", row.totalScore))
                            .font(.title2)
                            .fontWeight(.bold)
                            .monospacedDigit()
                    }
                }
            }
        }
        .navigationTitle("events.scoreboard")
        .refreshable { await load() }
        .task { await load() }
    }

    private func load() async {
        let repo = CompetitionRepository(apiClient: appState.apiClient)
        do {
            let response = try await repo.scoreboard(competitionId: competition.id)
            rows = response.data
            scoringUnit = response.scoringUnit
        } catch {}

        // Load member names from cache.
        if let tenantId = appState.session?.tenant.id, let db = appState.localDatabase {
            let cached = (try? db.cachedMembers(tenantId: tenantId)) ?? []
            members = Dictionary(uniqueKeysWithValues: cached.map { ($0.id, $0) })
        }
        isLoading = false
    }

    private func memberName(_ id: String) -> String {
        members[id]?.fullName ?? id.prefix(8) + "…"
    }
}
