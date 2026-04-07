import Foundation

/// URLSession-based API client. Attaches Bearer tokens, decodes the
/// `{ "data": T }` / `{ "error": {...} }` envelope, and transparently refreshes
/// expired access tokens.
@MainActor
final class APIClient {
    private(set) var baseURL: URL
    private let tokenManager: TokenManager
    private let session: URLSession
    private let refreshMutex = AsyncMutex()

    /// Invoked after a failed refresh — typically clears session state.
    var onAuthExpired: (@Sendable () async -> Void)?

    init(baseURL: URL, tokenManager: TokenManager) {
        self.baseURL = baseURL
        self.tokenManager = tokenManager

        let configuration = URLSessionConfiguration.default
        configuration.timeoutIntervalForRequest = 20
        configuration.timeoutIntervalForResource = 60
        self.session = URLSession(configuration: configuration)
    }

    /// Point the client at a new backend. Callers are responsible for
    /// clearing any tokens tied to the previous host.
    func updateBaseURL(_ url: URL) {
        self.baseURL = url
    }

    // MARK: - Public request API

    /// Perform a request and decode `{"data": T}`.
    func request<T: Decodable & Sendable>(_ endpoint: Endpoint) async throws -> T {
        let data = try await performWithRetry(endpoint)
        return try decodeDataEnvelope(data)
    }

    /// Perform a request and decode the raw envelope (`ListResponse<T>` etc.).
    func requestRaw<T: Decodable & Sendable>(_ endpoint: Endpoint) async throws -> T {
        let data = try await performWithRetry(endpoint)
        do {
            return try JSONDecoder.apiDecoder.decode(T.self, from: data)
        } catch let error as DecodingError {
            throw APIError.decoding(String(describing: error))
        } catch {
            throw APIError.decoding(error.localizedDescription)
        }
    }

    /// Perform a request without caring about the response body.
    func requestVoid(_ endpoint: Endpoint) async throws {
        _ = try await performWithRetry(endpoint)
    }

    // MARK: - Core request loop

    private func performWithRetry(_ endpoint: Endpoint) async throws -> Data {
        do {
            return try await performOnce(endpoint)
        } catch APIError.unauthorized where endpoint.requiresAuth {
            try await refreshAccessToken()
            return try await performOnce(endpoint)
        }
    }

    private func performOnce(_ endpoint: Endpoint) async throws -> Data {
        let request = try buildURLRequest(for: endpoint)

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch let urlError as URLError {
            throw APIError.network(urlError)
        } catch {
            throw APIError.network(URLError(.unknown))
        }

        guard let http = response as? HTTPURLResponse else {
            throw APIError.network(URLError(.badServerResponse))
        }

        if (200..<300).contains(http.statusCode) {
            return data
        }

        if http.statusCode == 401 {
            throw APIError.unauthorized
        }

        // Error envelope
        if let envelope = try? JSONDecoder.apiDecoder.decode(ErrorEnvelope.self, from: data) {
            if envelope.error.code == "PRECONDITION_FAILED" {
                throw APIError.noActiveTenant
            }
            throw APIError.server(
                status: http.statusCode,
                code: envelope.error.code,
                message: envelope.error.message
            )
        }

        throw APIError.server(status: http.statusCode, code: "UNKNOWN", message: "Request failed")
    }

    // MARK: - Refresh flow

    private func refreshAccessToken() async throws {
        try await refreshMutex.runExclusive {
            guard let refreshToken = self.tokenManager.refreshToken else {
                await self.handleAuthExpired()
                throw APIError.unauthorized
            }

            do {
                let envelope: DataEnvelope<TokenPair> = try await self.performRefreshCall(
                    refreshToken: refreshToken
                )
                self.tokenManager.updateTokens(
                    access: envelope.data.accessToken,
                    refresh: envelope.data.refreshToken
                )
            } catch {
                await self.handleAuthExpired()
                throw APIError.unauthorized
            }
        }
    }

    /// Dedicated refresh call — bypasses the retry loop to avoid recursion.
    private func performRefreshCall<T: Decodable & Sendable>(
        refreshToken: String
    ) async throws -> T {
        let endpoint = Endpoint.refresh(refreshToken: refreshToken)
        let request = try buildURLRequest(for: endpoint)

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw APIError.unauthorized
        }
        return try JSONDecoder.apiDecoder.decode(T.self, from: data)
    }

    private func handleAuthExpired() async {
        await onAuthExpired?()
    }

    // MARK: - Request building

    private func buildURLRequest(for endpoint: Endpoint) throws -> URLRequest {
        var components = URLComponents(
            url: baseURL.appendingPathComponent(endpoint.path),
            resolvingAgainstBaseURL: false
        )
        if !endpoint.query.isEmpty {
            components?.queryItems = endpoint.query
        }
        guard let url = components?.url else {
            throw APIError.network(URLError(.badURL))
        }

        var request = URLRequest(url: url)
        request.httpMethod = endpoint.method.rawValue
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if let body = endpoint.body {
            request.httpBody = body
        }
        if endpoint.requiresAuth, let token = tokenManager.accessToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        return request
    }

    // MARK: - Envelope decoding

    private func decodeDataEnvelope<T: Decodable & Sendable>(_ data: Data) throws -> T {
        do {
            let envelope = try JSONDecoder.apiDecoder.decode(DataEnvelope<T>.self, from: data)
            return envelope.data
        } catch let error as DecodingError {
            throw APIError.decoding(String(describing: error))
        } catch {
            throw APIError.decoding(error.localizedDescription)
        }
    }
}

// MARK: - Envelope types

nonisolated private struct DataEnvelope<T: Decodable & Sendable>: Decodable, Sendable {
    let data: T
}

nonisolated private struct ErrorEnvelope: Decodable {
    struct ErrorBody: Decodable {
        let code: String
        let message: String
    }
    let error: ErrorBody
}

nonisolated private struct TokenPair: Decodable, Sendable {
    let accessToken: String
    let refreshToken: String
}

// MARK: - AsyncMutex

/// Coalesces concurrent refresh calls: only one refresh runs at a time,
/// concurrent callers await the same attempt.
actor AsyncMutex {
    private var task: Task<Void, Error>?

    func runExclusive(_ operation: @Sendable @escaping () async throws -> Void) async throws {
        if let existing = task {
            try await existing.value
            return
        }
        let newTask = Task { try await operation() }
        task = newTask
        defer { task = nil }
        try await newTask.value
    }
}

// MARK: - JSON helpers

nonisolated extension JSONDecoder {
    static let apiDecoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        decoder.dateDecodingStrategy = .iso8601
        return decoder
    }()
}

nonisolated extension JSONEncoder {
    static let snake: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        encoder.dateEncodingStrategy = .iso8601
        return encoder
    }()
}
