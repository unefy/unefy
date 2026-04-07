import Foundation

/// Runtime-overridable API base URL. The user can change this at login
/// (e.g. to point at their self-hosted unefy instance). Persisted in
/// UserDefaults — not sensitive, no need for Keychain.
nonisolated final class ServerConfig: @unchecked Sendable {
    private let defaults: UserDefaults
    private let storageKey = "de.unefy.app.serverURL"
    private let lock = NSLock()

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
    }

    /// Current API base URL — either the user's override or the build default.
    var currentURL: URL {
        lock.lock()
        defer { lock.unlock() }
        if let raw = defaults.string(forKey: storageKey),
           let url = URL(string: raw) {
            return url
        }
        return AppConfig.apiBaseURL
    }

    /// String form of the current URL for display / editing.
    var currentURLString: String {
        currentURL.absoluteString
    }

    /// Validate + persist a new URL. Returns the parsed URL on success.
    @discardableResult
    func update(from raw: String) throws -> URL {
        let trimmed = raw.trimmingCharacters(in: .whitespaces)
            .trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        guard let url = URL(string: trimmed),
              let scheme = url.scheme?.lowercased(),
              scheme == "http" || scheme == "https",
              url.host?.isEmpty == false
        else {
            throw ServerConfigError.invalidURL
        }
        lock.lock()
        defaults.set(url.absoluteString, forKey: storageKey)
        lock.unlock()
        return url
    }

    /// Revert to the build-default URL.
    func reset() {
        lock.lock()
        defaults.removeObject(forKey: storageKey)
        lock.unlock()
    }
}

enum ServerConfigError: Error {
    case invalidURL
}
