import SwiftUI

struct MemberListView: View {
    @Environment(AppState.self) private var appState
    @State private var viewModel: MembersViewModel?
    @State private var showCreateSheet = false
    @State private var memberToDelete: Member?

    var body: some View {
        NavigationStack {
            content
            .navigationTitle(appState.session?.tenant.name ?? "members.title")
            .toolbar {
                if let vm = viewModel, !vm.availableStatusCounts.isEmpty {
                    ToolbarItem(placement: .topBarLeading) {
                        statusFilterMenu(vm: vm)
                    }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    HStack(spacing: 12) {
                        Button { showCreateSheet = true } label: {
                            Image(systemName: "plus")
                        }
                        Menu {
                            Button(role: .destructive) {
                                Task { await appState.logout() }
                            } label: {
                                Label("auth.signOut", systemImage: "rectangle.portrait.and.arrow.right")
                            }
                        } label: {
                            Image(systemName: "person.crop.circle")
                        }
                    }
                }
                if let vm = viewModel, vm.state == .loaded {
                    ToolbarItem(placement: .bottomBar) {
                        SyncStatusLabel(
                            lastSyncedAt: vm.lastSyncedAt,
                            fromCache: vm.showingCachedData
                        )
                    }
                }
            }
            .searchable(
                text: Binding(
                    get: { viewModel?.searchText ?? "" },
                    set: { viewModel?.searchText = $0 }
                ),
                prompt: Text("members.searchPlaceholder")
            )
            .refreshable {
                await viewModel?.refresh()
            }
            .task {
                if viewModel == nil, let vm = makeViewModel() {
                    viewModel = vm
                }
                await viewModel?.loadInitial()
            }
            .sheet(isPresented: $showCreateSheet) {
                MemberFormView(existingMember: nil) {
                    await viewModel?.refresh()
                }
            }
            .alert(
                "members.confirmDelete",
                isPresented: .init(
                    get: { memberToDelete != nil },
                    set: { if !$0 { memberToDelete = nil } }
                )
            ) {
                Button("members.deleteAction", role: .destructive) {
                    if let member = memberToDelete {
                        Task { await deleteMember(member) }
                    }
                }
                Button("common.cancel", role: .cancel) {}
            }
        }
    }

    private func deleteMember(_ member: Member) async {
        do {
            try await appState.apiClient.requestVoid(.deleteMember(id: member.id))
            await viewModel?.refresh()
        } catch {}
    }

    private func makeViewModel() -> MembersViewModel? {
        guard
            let tenantId = appState.session?.tenant.id,
            let localDB = appState.localDatabase
        else { return nil }
        let repository = MemberRepository(
            apiClient: appState.apiClient,
            localDB: localDB,
            tenantId: tenantId
        )
        return MembersViewModel(repository: repository)
    }

    @ViewBuilder
    private var content: some View {
        if let vm = viewModel {
            switch vm.state {
            case .idle:
                LoadingState()
            case .loading where vm.members.isEmpty:
                LoadingState()
            case .error(let message) where vm.members.isEmpty:
                ErrorView(message: message) {
                    Task { await vm.refresh() }
                }
            case .loaded where vm.members.isEmpty:
                EmptyState(
                    systemImage: "person.2",
                    title: String(localized: "members.emptyTitle"),
                    message: String(localized: "members.emptyMessage")
                )
            default:
                membersList(vm: vm)
            }
        } else {
            LoadingState()
        }
    }

    private func statusFilterMenu(vm: MembersViewModel) -> some View {
        Menu {
            Button {
                vm.statusFilter = nil
            } label: {
                Label(
                    "members.filterAll",
                    systemImage: vm.statusFilter == nil ? "checkmark" : ""
                )
            }
            Divider()
            ForEach(
                vm.availableStatusCounts.sorted { $0.key < $1.key },
                id: \.key
            ) { entry in
                Button {
                    vm.statusFilter = entry.key
                } label: {
                    HStack {
                        if vm.statusFilter == entry.key {
                            Image(systemName: "checkmark")
                        }
                        Text("\(entry.key) (\(entry.value))")
                    }
                }
            }
        } label: {
            Image(systemName: vm.statusFilter == nil
                  ? "line.3.horizontal.decrease.circle"
                  : "line.3.horizontal.decrease.circle.fill")
        }
    }

    private func membersList(vm: MembersViewModel) -> some View {
        List {
            ForEach(vm.members) { member in
                NavigationLink(value: member) {
                    MemberRow(member: member)
                }
                .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                    Button(role: .destructive) {
                        memberToDelete = member
                    } label: {
                        Label("members.deleteAction", systemImage: "trash")
                    }
                }
                .task {
                    await vm.loadMoreIfNeeded(currentItem: member)
                }
            }

            if vm.isLoadingMore {
                HStack {
                    Spacer()
                    ProgressView()
                    Spacer()
                }
            }
        }
        .navigationDestination(for: Member.self) { member in
            MemberDetailView(member: member)
        }
    }
}

private struct MemberRow: View {
    let member: Member

    var body: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                Text(member.fullName)
                    .font(.body)
                    .fontWeight(.medium)
                HStack(spacing: 6) {
                    Text("#\(member.memberNumber)")
                    if let email = member.email {
                        Text("·")
                        Text(email)
                            .lineLimit(1)
                            .truncationMode(.middle)
                    }
                }
                .font(.caption)
                .foregroundStyle(.secondary)
            }
            Spacer()
            StatusBadge(status: member.status)
        }
        .padding(.vertical, 2)
    }
}

private struct StatusBadge: View {
    let status: String

    var body: some View {
        Text(status)
            .font(.caption2)
            .fontWeight(.medium)
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
            .background(color.opacity(0.15), in: .capsule)
            .foregroundStyle(color)
    }

    private var color: Color {
        switch status.lowercased() {
        case "active": .green
        case "inactive", "left": .gray
        case "deceased": .secondary
        default: .blue
        }
    }
}

#Preview {
    MemberListView()
        .environment(AppState())
}
