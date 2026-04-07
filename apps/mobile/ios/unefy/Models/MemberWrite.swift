import Foundation

/// Body for POST /api/v1/members.
nonisolated struct MemberCreatePayload: Codable, Sendable {
    let firstName: String
    let lastName: String
    let email: String?
    let phone: String?
    let mobile: String?
    let birthday: String?
    let street: String?
    let zipCode: String?
    let city: String?
    let state: String?
    let country: String?
    let joinedAt: String?
    let status: String
    let category: String?
    let notes: String?
}

/// Body for PATCH /api/v1/members/{id}. All fields optional.
nonisolated struct MemberUpdatePayload: Codable, Sendable {
    let firstName: String?
    let lastName: String?
    let email: String?
    let phone: String?
    let mobile: String?
    let birthday: String?
    let street: String?
    let zipCode: String?
    let city: String?
    let state: String?
    let country: String?
    let joinedAt: String?
    let status: String?
    let category: String?
    let notes: String?
}
