import Foundation

/// All errors surfaced by the API client. Views map these to localized messages
/// via `ErrorMessageMapper`.
enum APIError: Error, Sendable {
    /// Network transport failure (no connection, timeout, DNS, …).
    case network(URLError)
    /// Response body could not be decoded.
    case decoding(String)
    /// Backend returned `{ "error": { code, message } }`.
    case server(status: Int, code: String, message: String)
    /// 401 Unauthorized. After automatic refresh attempt exhausted.
    case unauthorized
    /// User has no active tenant membership (412 PRECONDITION_FAILED).
    case noActiveTenant
}

extension APIError {
    var isAuthExpired: Bool {
        switch self {
        case .unauthorized: true
        default: false
        }
    }

    var code: String {
        switch self {
        case .network: "NETWORK"
        case .decoding: "DECODING"
        case .server(_, let code, _): code
        case .unauthorized: "UNAUTHORIZED"
        case .noActiveTenant: "PRECONDITION_FAILED"
        }
    }
}
