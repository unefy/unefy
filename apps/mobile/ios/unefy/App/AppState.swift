import Foundation
import Observation

/// Root app state. Holds the authenticated session and coordinates login/logout.
@MainActor
@Observable
final class AppState {
    private(set) var session: Session?
    private(set) var isRestoring: Bool = true

    var isAuthenticated: Bool { session != nil }

    private let tokenManager: TokenManager
    private(set) var apiClient: APIClient
    let serverConfig: ServerConfig
    let localDatabase: LocalDatabase?
    let networkMonitor: NetworkMonitor
    private(set) var syncEngine: ResultSyncEngine?

    init() {
        let tokenManager = TokenManager()
        let serverConfig = ServerConfig()
        self.tokenManager = tokenManager
        self.serverConfig = serverConfig
        self.localDatabase = try? LocalDatabase()
        self.networkMonitor = NetworkMonitor()
        self.apiClient = APIClient(
            baseURL: serverConfig.currentURL,
            tokenManager: tokenManager
        )
        self.apiClient.onAuthExpired = { [weak self] in
            await self?.logoutLocally()
        }
        if let db = localDatabase {
            let engine = ResultSyncEngine(
                apiClient: apiClient,
                context: db.context,
                networkMonitor: networkMonitor
            )
            self.syncEngine = engine
            engine.start()
        }
    }

    /// Called on app launch. Tries to restore a session from the keychain.
    func restore() async {
        defer { isRestoring = false }

        guard tokenManager.hasTokens else { return }

        do {
            let me: MeResponse = try await apiClient.requestRaw(.me)
            guard
                let payload = me.data,
                let tenantId = payload.tenantId,
                let tenantName = payload.tenantName,
                let role = payload.role
            else {
                await logoutLocally()
                return
            }
            self.session = Session(
                user: payload.user,
                tenant: Tenant(
                    id: tenantId,
                    name: tenantName,
                    slug: nil,
                    shortName: payload.tenantShortName
                ),
                role: role
            )
        } catch {
            await logoutLocally()
        }
    }

    func setSession(
        accessToken: String,
        refreshToken: String,
        user: User,
        tenant: Tenant,
        role: String
    ) {
        tokenManager.save(accessToken: accessToken, refreshToken: refreshToken)
        self.session = Session(user: user, tenant: tenant, role: role)
    }

    /// Change the backend URL. Any existing tokens + cache are cleared
    /// since they belong to a different server.
    func updateServerURL(from raw: String) throws {
        let url = try serverConfig.update(from: raw)
        tokenManager.clear()
        try? localDatabase?.clearAll()
        session = nil
        apiClient.updateBaseURL(url)
    }

    func logout() async {
        if let refreshToken = tokenManager.refreshToken {
            _ = try? await apiClient.requestVoid(.logout(refreshToken: refreshToken))
        }
        await logoutLocally()
    }

    fileprivate func logoutLocally() async {
        tokenManager.clear()
        try? localDatabase?.clearAll()  // GDPR: no member data remains after logout
        self.session = nil
    }
}
