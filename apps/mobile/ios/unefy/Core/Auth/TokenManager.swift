import Foundation
import Security

/// Stores access + refresh tokens in the iOS Keychain.
/// Never use UserDefaults for tokens.
nonisolated final class TokenManager: @unchecked Sendable {
    private let service = "de.unefy.app.tokens"
    private let accessAccount = "unefy.access"
    private let refreshAccount = "unefy.refresh"
    private let lock = NSLock()

    var accessToken: String? {
        read(account: accessAccount)
    }

    var refreshToken: String? {
        read(account: refreshAccount)
    }

    var hasTokens: Bool {
        accessToken != nil && refreshToken != nil
    }

    func save(accessToken: String, refreshToken: String) {
        lock.lock()
        defer { lock.unlock() }
        write(value: accessToken, account: accessAccount)
        write(value: refreshToken, account: refreshAccount)
    }

    func updateAccessToken(_ token: String) {
        lock.lock()
        defer { lock.unlock() }
        write(value: token, account: accessAccount)
    }

    func updateTokens(access: String, refresh: String) {
        lock.lock()
        defer { lock.unlock() }
        write(value: access, account: accessAccount)
        write(value: refresh, account: refreshAccount)
    }

    func clear() {
        lock.lock()
        defer { lock.unlock() }
        delete(account: accessAccount)
        delete(account: refreshAccount)
    }

    // MARK: - Keychain primitives

    private func baseQuery(account: String) -> [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
    }

    private func read(account: String) -> String? {
        var query = baseQuery(account: account)
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne

        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        guard status == errSecSuccess, let data = item as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    private func write(value: String, account: String) {
        let data = Data(value.utf8)
        let query = baseQuery(account: account)

        let attributes: [String: Any] = [
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly,
        ]

        let status = SecItemUpdate(query as CFDictionary, attributes as CFDictionary)
        if status == errSecItemNotFound {
            var insert = query
            insert[kSecValueData as String] = data
            insert[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
            SecItemAdd(insert as CFDictionary, nil)
        }
    }

    private func delete(account: String) {
        SecItemDelete(baseQuery(account: account) as CFDictionary)
    }
}
