import Foundation

/// Reads compile-time configuration from Info.plist.
/// Values are injected from `Config/Dev.xcconfig` / `Config/Prod.xcconfig`.
nonisolated enum AppConfig {
    static let apiBaseURL: URL = {
        guard
            let raw = Bundle.main.object(forInfoDictionaryKey: "API_BASE_URL") as? String,
            let url = URL(string: raw)
        else {
            fatalError("API_BASE_URL missing in Info.plist — check xcconfig wiring")
        }
        return url
    }()

    static var isDebugBuild: Bool {
        #if DEBUG
        true
        #else
        false
        #endif
    }
}
