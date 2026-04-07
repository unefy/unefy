import Foundation
import Network
import Observation

/// Observes reachability. `isOnline` is a best-effort signal — it does
/// not guarantee the backend is reachable, only that some network
/// interface is up. Real failures still come from API calls.
@MainActor
@Observable
final class NetworkMonitor {
    private(set) var isOnline: Bool = true

    private let monitor = NWPathMonitor()
    private let queue = DispatchQueue(label: "de.unefy.app.network-monitor")

    init() {
        monitor.pathUpdateHandler = { [weak self] path in
            let online = path.status == .satisfied
            Task { @MainActor in
                self?.isOnline = online
            }
        }
        monitor.start(queue: queue)
    }

    deinit {
        monitor.cancel()
    }
}
