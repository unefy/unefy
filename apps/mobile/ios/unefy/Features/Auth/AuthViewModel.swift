import Foundation
import Observation

@MainActor
@Observable
final class AuthViewModel {
    var email: String = ""
    private(set) var isLoading: Bool = false
    private(set) var errorMessage: String?

    private let service: AuthService
    private let appState: AppState

    init(appState: AppState) {
        self.appState = appState
        self.service = AuthService(apiClient: appState.apiClient)
    }

    var canSubmit: Bool {
        !isLoading && isEmailValid
    }

    private var isEmailValid: Bool {
        let trimmed = email.trimmingCharacters(in: .whitespaces)
        guard trimmed.contains("@"), trimmed.contains(".") else { return false }
        return trimmed.count >= 5
    }

    func login() async {
        guard canSubmit else { return }
        let trimmed = email.trimmingCharacters(in: .whitespaces)

        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            let response = try await service.devLogin(email: trimmed)
            appState.setSession(
                accessToken: response.accessToken,
                refreshToken: response.refreshToken,
                user: response.user,
                tenant: response.tenant,
                role: response.role
            )
        } catch let error as APIError {
            errorMessage = ErrorMessageMapper.message(for: error)
        } catch {
            errorMessage = String(localized: "errors.unknown")
        }
    }
}
