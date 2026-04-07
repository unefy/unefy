import SwiftUI

struct RootView: View {
    @Environment(AppState.self) private var appState

    var body: some View {
        Group {
            if appState.isRestoring {
                ProgressView()
                    .controlSize(.large)
            } else if appState.isAuthenticated {
                MainTabView()
            } else {
                LoginView()
            }
        }
        .animation(.default, value: appState.isAuthenticated)
        .animation(.default, value: appState.isRestoring)
    }
}

#Preview {
    RootView()
        .environment(AppState())
}
