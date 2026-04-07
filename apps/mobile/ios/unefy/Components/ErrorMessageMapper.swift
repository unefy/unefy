import Foundation

enum ErrorMessageMapper {
    static func message(for error: APIError) -> String {
        let base = baseMessage(for: error)
        #if DEBUG
        return "\(base)\n\n[DEBUG] \(debugDetails(for: error))"
        #else
        return base
        #endif
    }

    private static func baseMessage(for error: APIError) -> String {
        switch error {
        case .network:
            String(localized: "errors.network")
        case .decoding:
            String(localized: "errors.unknown")
        case .unauthorized:
            String(localized: "errors.unauthorized")
        case .noActiveTenant:
            String(localized: "errors.noActiveTenant")
        case .server(_, let code, _):
            messageForCode(code)
        }
    }

    private static func debugDetails(for error: APIError) -> String {
        switch error {
        case .network(let urlError):
            "network: \(urlError.code.rawValue) \(urlError.localizedDescription)"
        case .decoding(let detail):
            "decoding: \(detail)"
        case .unauthorized:
            "unauthorized (after refresh)"
        case .noActiveTenant:
            "412 PRECONDITION_FAILED"
        case .server(let status, let code, let message):
            "HTTP \(status) \(code): \(message)"
        }
    }

    private static func messageForCode(_ code: String) -> String {
        switch code {
        case "NOT_FOUND": String(localized: "errors.notFound")
        case "FORBIDDEN": String(localized: "errors.forbidden")
        case "CONFLICT": String(localized: "errors.conflict")
        case "VALIDATION_ERROR": String(localized: "errors.validation")
        case "INVALID_TOKEN": String(localized: "errors.unauthorized")
        case "PRECONDITION_FAILED": String(localized: "errors.noActiveTenant")
        default: String(localized: "errors.unknown")
        }
    }
}
