import SwiftUI

struct LoginView: View {
    @Environment(AppState.self) private var appState
    @State private var viewModel: AuthViewModel?
    @State private var serverURL: String = ""
    @State private var serverURLError: String?

    var body: some View {
        NavigationStack {
            Form {
                serverSection
                emailSection
                errorSection
                submitSection
            }
            .navigationTitle("auth.welcome")
            .onAppear {
                if viewModel == nil {
                    viewModel = AuthViewModel(appState: appState)
                }
                if serverURL.isEmpty {
                    serverURL = appState.serverConfig.currentURLString
                }
            }
        }
    }

    // MARK: - Sections

    private var serverSection: some View {
        Section {
            TextField(
                String(localized: "auth.serverURLPlaceholder"),
                text: $serverURL
            )
            .keyboardType(.URL)
            .textContentType(.URL)
            .textInputAutocapitalization(.never)
            .autocorrectionDisabled()
            .onChange(of: serverURL) { _, _ in
                serverURLError = nil
            }
            .onSubmit(persistServerURL)
        } header: {
            Text("auth.serverLabel")
        } footer: {
            if let error = serverURLError {
                Text(error)
                    .foregroundStyle(.red)
            } else {
                Text("auth.serverHint")
            }
        }
    }

    private var emailSection: some View {
        Section {
            TextField(
                String(localized: "auth.emailLabel"),
                text: Binding(
                    get: { viewModel?.email ?? "" },
                    set: { viewModel?.email = $0 }
                )
            )
            .keyboardType(.emailAddress)
            .textContentType(.emailAddress)
            .textInputAutocapitalization(.never)
            .autocorrectionDisabled()
        } header: {
            Text("auth.emailLabel")
        } footer: {
            if AppConfig.isDebugBuild {
                Label(
                    String(localized: "auth.devModeNotice"),
                    systemImage: "wrench.and.screwdriver"
                )
                .font(.caption)
                .foregroundStyle(.orange)
            }
        }
    }

    @ViewBuilder
    private var errorSection: some View {
        if let error = viewModel?.errorMessage {
            Section {
                Text(error)
                    .foregroundStyle(.red)
                    .font(.callout)
            }
        }
    }

    private var submitSection: some View {
        Section {
            Button(action: submit) {
                HStack {
                    Spacer()
                    if viewModel?.isLoading == true {
                        ProgressView()
                    } else {
                        Text("auth.signIn")
                            .fontWeight(.semibold)
                    }
                    Spacer()
                }
            }
            .disabled(viewModel?.canSubmit != true)
        }
    }

    // MARK: - Actions

    private func submit() {
        persistServerURL()
        guard serverURLError == nil else { return }
        Task { await viewModel?.login() }
    }

    private func persistServerURL() {
        let desired = serverURL.trimmingCharacters(in: .whitespaces)
        guard desired != appState.serverConfig.currentURLString else { return }
        do {
            try appState.updateServerURL(from: desired)
            serverURLError = nil
        } catch {
            serverURLError = String(localized: "auth.serverURLInvalid")
        }
    }
}

#Preview {
    LoginView()
        .environment(AppState())
}
