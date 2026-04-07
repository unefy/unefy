import Foundation

nonisolated struct Member: Codable, Sendable, Identifiable, Equatable, Hashable {
    let id: String
    let memberNumber: String
    let firstName: String
    let lastName: String
    let email: String?
    let phone: String?
    let mobile: String?
    let birthday: String?  // ISO date — keep as string for simple list display
    let street: String?
    let zipCode: String?
    let city: String?
    let state: String?
    let country: String?
    let joinedAt: String
    let leftAt: String?
    let status: String
    let category: String?
    let notes: String?
    let userId: String?
    let createdAt: Date
    let updatedAt: Date

    var fullName: String {
        "\(firstName) \(lastName)".trimmingCharacters(in: .whitespaces)
    }
}
