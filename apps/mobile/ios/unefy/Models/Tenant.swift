import Foundation

nonisolated struct Tenant: Codable, Sendable, Identifiable, Equatable {
    let id: String
    let name: String
    let slug: String?
    let shortName: String?
}
