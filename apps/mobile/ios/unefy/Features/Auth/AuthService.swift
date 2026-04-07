import Foundation

@MainActor
struct AuthService {
    let apiClient: APIClient

    func devLogin(email: String) async throws -> LoginResponse {
        try await apiClient.request(.devLogin(email: email))
    }
}
