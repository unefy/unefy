import SwiftUI

struct SessionDetailView: View {
    let competition: Competition
    let session: CompetitionSession
    @Environment(AppState.self) private var appState
    @State private var viewModel: SessionDetailViewModel?
    @State private var showEntryForm = false
    @State private var showScanner = false
    @State private var showShotEntry = false
    @State private var showLiveScanner = false

    var body: some View {
        List {
            if let vm = viewModel {
                if vm.state == .loading && vm.displayEntries.isEmpty {
                    ProgressView()
                } else if vm.displayEntries.isEmpty {
                    Text("events.noResults")
                        .foregroundStyle(.secondary)
                } else {
                    ForEach(vm.displayEntries) { entry in
                        NavigationLink(value: entry.id) {
                            EntryListRow(entry: entry, scoringUnit: competition.scoringUnit)
                        }
                        .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                            Button(role: .destructive) {
                                Task {
                                    try? await appState.apiClient.requestVoid(
                                        .deleteEntry(
                                            competitionId: competition.id,
                                            sessionId: session.id,
                                            entryId: entry.id
                                        )
                                    )
                                    await vm.load()
                                }
                            } label: {
                                Label("common.delete", systemImage: "trash")
                            }
                        }
                    }
                }
            }
        }
        .navigationTitle(session.name ?? session.displayDate ?? session.date)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Menu {
                    Button { showLiveScanner = true } label: {
                        Label("scanner.liveTitle", systemImage: "camera.viewfinder")
                    }
                    Button { showShotEntry = true } label: {
                        Label("scoring.targetEntry", systemImage: "scope")
                    }
                    Button { showEntryForm = true } label: {
                        Label("scoring.manualEntry", systemImage: "number")
                    }
                    Button { showScanner = true } label: {
                        Label("scanner.photoTitle", systemImage: "photo")
                    }
                } label: {
                    Image(systemName: "plus.circle")
                }
            }
        }
        .navigationDestination(for: String.self) { entryId in
            if let entry = viewModel?.displayEntries.first(where: { $0.id == entryId }) {
                EntryDetailView(
                    entry: entry,
                    competition: competition,
                    session: session,
                    onChanged: { await viewModel?.load() }
                )
            }
        }
        .refreshable { await viewModel?.load() }
        .task {
            if viewModel == nil {
                viewModel = SessionDetailViewModel(
                    competition: competition, session: session,
                    apiClient: appState.apiClient,
                    localDB: appState.localDatabase,
                    tenantId: appState.session?.tenant.id ?? ""
                )
            }
            await viewModel?.load()
        }
        .task(id: "sync-watcher") {
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(2))
                if Task.isCancelled { break }
                let hasPending = viewModel?.displayEntries.contains { $0.syncState != .synced } ?? false
                if hasPending { await viewModel?.load() }
            }
        }
        .sheet(isPresented: $showEntryForm) {
            EntryFormView(competition: competition, session: session) {
                await viewModel?.load()
            }
        }
        .fullScreenCover(isPresented: $showShotEntry) {
            ShotEntryView(competition: competition, session: session) {
                await viewModel?.load()
            }
        }
        .sheet(isPresented: $showScanner) {
            ScannerView(competition: competition, session: session) {
                await viewModel?.load()
            }
        }
        .fullScreenCover(isPresented: $showLiveScanner) {
            LiveScannerView(competition: competition, session: session) {
                await viewModel?.load()
            }
        }
    }
}

// MARK: - List Row (compact, no target image)

private struct EntryListRow: View {
    let entry: DisplayEntry
    let scoringUnit: String

    var body: some View {
        HStack(spacing: 12) {
            // Left: discipline + meta
            VStack(alignment: .leading, spacing: 3) {
                if let discipline = entry.discipline, !discipline.isEmpty {
                    Text(discipline)
                        .font(.body)
                        .fontWeight(.medium)
                }
                HStack(spacing: 6) {
                    if let shots = entry.details?.shots {
                        Text("\(shots.count) \(String(localized: "events.shotsLabel"))")
                    }
                    Text(scoringUnit)
                }
                .font(.caption)
                .foregroundStyle(.secondary)
            }

            Spacer()

            // Right: score + sync
            HStack(alignment: .firstTextBaseline, spacing: 6) {
                syncIndicator
                Text(String(format: "%.0f", entry.scoreValue))
                    .font(.title3)
                    .fontWeight(.bold)
                    .monospacedDigit()
                    .foregroundStyle(entry.syncState == .synced ? .primary : .secondary)
            }
        }
        .padding(.vertical, 2)
    }

    @ViewBuilder
    private var syncIndicator: some View {
        switch entry.syncState {
        case .synced:
            if entry.source == "scan" {
                Image(systemName: "camera.viewfinder")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        case .pending, .uploading:
            ProgressView().controlSize(.mini)
        case .failed:
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.caption)
                .foregroundStyle(.red)
        }
    }
}
