import SwiftUI

struct CompetitionListView: View {
    @Environment(AppState.self) private var appState
    @State private var viewModel: CompetitionsViewModel?
    @State private var showCreateSheet = false
    @State private var competitionToDelete: Competition?

    var body: some View {
        NavigationStack {
            content
                .navigationTitle("events.title")
                .toolbar {
                    ToolbarItem(placement: .topBarTrailing) {
                        Button { showCreateSheet = true } label: {
                            Image(systemName: "plus")
                        }
                    }
                }
                .refreshable { await viewModel?.refresh() }
                .task {
                    if viewModel == nil {
                        viewModel = CompetitionsViewModel(apiClient: appState.apiClient, context: appState.localDatabase?.context)
                    }
                    await viewModel?.loadInitial()
                }
                .sheet(isPresented: $showCreateSheet) {
                    CreateCompetitionSheet { await viewModel?.refresh() }
                }
                .alert(
                    "events.confirmDelete",
                    isPresented: .init(
                        get: { competitionToDelete != nil },
                        set: { if !$0 { competitionToDelete = nil } }
                    )
                ) {
                    Button("common.delete", role: .destructive) {
                        if let comp = competitionToDelete {
                            Task {
                                try? await appState.apiClient.requestVoid(.deleteCompetition(id: comp.id))
                                await viewModel?.refresh()
                            }
                        }
                    }
                    Button("common.cancel", role: .cancel) {}
                } message: {
                    Text(competitionToDelete?.name ?? "")
                }
        }
    }

    @ViewBuilder
    private var content: some View {
        if let vm = viewModel {
            switch vm.state {
            case .idle, .loading where vm.competitions.isEmpty:
                LoadingState()
            case .error(let msg) where vm.competitions.isEmpty:
                ErrorView(message: msg) { Task { await vm.refresh() } }
            case .loaded where vm.competitions.isEmpty:
                EmptyState(systemImage: "calendar", title: String(localized: "events.emptyTitle"), message: String(localized: "events.emptyMessage"))
            default:
                List {
                    ForEach(vm.competitions) { comp in
                        NavigationLink(value: comp) {
                            CompetitionRow(competition: comp)
                        }
                        .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                            Button(role: .destructive) {
                                competitionToDelete = comp
                            } label: {
                                Label("common.delete", systemImage: "trash")
                            }
                        }
                    }
                }
                .navigationDestination(for: Competition.self) { comp in
                    CompetitionDetailView(competition: comp)
                }
            }
        } else {
            LoadingState()
        }
    }
}

private struct CompetitionRow: View {
    let competition: Competition

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(competition.name)
                    .font(.body)
                    .fontWeight(.medium)
                Spacer()
                Text(typeBadge)
                    .font(.caption2)
                    .fontWeight(.medium)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(typeColor.opacity(0.15), in: .capsule)
                    .foregroundStyle(typeColor)
            }
            HStack(spacing: 8) {
                if let date = competition.displayStartDate {
                    Text(date)
                }
                if let disciplines = competition.disciplines, !disciplines.isEmpty {
                    Text("·")
                    Text(disciplines.joined(separator: ", "))
                        .lineLimit(1)
                }
            }
            .font(.caption)
            .foregroundStyle(.secondary)
        }
        .padding(.vertical, 2)
    }

    private var typeBadge: String {
        switch competition.competitionType {
        case "league": "Liga"
        case "training": "Training"
        default: "Wettkampf"
        }
    }

    private var typeColor: Color {
        switch competition.competitionType {
        case "league": .blue
        case "training": .green
        default: .orange
        }
    }
}
