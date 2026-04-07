import Foundation

nonisolated struct User: Codable, Sendable, Identifiable, Equatable {
    let id: String
    let name: String
    let email: String
    let image: String?
    let locale: String?
}
