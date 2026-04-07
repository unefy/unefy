import SwiftUI

struct MainTabView: View {
    @Environment(AppState.self) private var appState

    var body: some View {
        TabView {
            Tab("nav.members", systemImage: "person.2") {
                MemberListView()
            }

            Tab("nav.events", systemImage: "calendar") {
                CompetitionListView()
            }
        }
        .tabViewStyle(.sidebarAdaptable)
        .overlay(alignment: .top) {
            GlobalSyncBanner()
                .padding(.top, 4)
        }
    }
}

#Preview {
    MainTabView()
        .environment(AppState())
}
