import Foundation

/// The currently authenticated user + tenant context.
/// Tokens are stored separately in the Keychain via `TokenManager`.
nonisolated struct Session: Sendable, Equatable {
    let user: User
    let tenant: Tenant
    let role: String
}

/// Payload returned by POST /api/v1/auth/mobile/dev/login (and /refresh).
/// This is what lives inside `{ "data": { ... } }`.
nonisolated struct LoginResponse: Decodable, Sendable {
    let accessToken: String
    let refreshToken: String
    let accessExpiresIn: Int
    let refreshExpiresIn: Int
    let user: User
    let tenant: Tenant
    let role: String
}

/// Payload of GET /api/v1/auth/me (inside the envelope).
/// Backend may return `null` when unauthenticated — caller handles `data == nil`.
nonisolated struct MePayload: Decodable, Sendable {
    let user: User
    let tenantId: String?
    let tenantName: String?
    let tenantShortName: String?
    let role: String?
    let needsOnboarding: Bool
}

/// Raw envelope for /auth/me (data may be null).
nonisolated struct MeResponse: Decodable, Sendable {
    let data: MePayload?
}
