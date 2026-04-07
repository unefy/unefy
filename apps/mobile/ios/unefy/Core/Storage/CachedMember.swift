import Foundation
import SwiftData

/// SwiftData mirror of `Member`. The API DTO (`Member` struct) stays the
/// boundary with the backend; this type is the on-disk cache.
///
/// Ownership: rows are owned by the current tenant. When the user logs out
/// or switches server, all rows are cleared.
@Model
final class CachedMember {
    #Unique<CachedMember>([\.id])

    @Attribute(.unique) var id: String
    var tenantId: String
    var memberNumber: String
    var firstName: String
    var lastName: String
    var email: String?
    var phone: String?
    var mobile: String?
    var birthday: String?
    var street: String?
    var zipCode: String?
    var city: String?
    var state: String?
    var country: String?
    var joinedAt: String
    var leftAt: String?
    var status: String
    var category: String?
    var notes: String?
    var userId: String?
    var createdAt: Date
    var updatedAt: Date
    /// When this row was last refreshed from the API.
    var cachedAt: Date

    init(from member: Member, tenantId: String, cachedAt: Date = .now) {
        self.id = member.id
        self.tenantId = tenantId
        self.memberNumber = member.memberNumber
        self.firstName = member.firstName
        self.lastName = member.lastName
        self.email = member.email
        self.phone = member.phone
        self.mobile = member.mobile
        self.birthday = member.birthday
        self.street = member.street
        self.zipCode = member.zipCode
        self.city = member.city
        self.state = member.state
        self.country = member.country
        self.joinedAt = member.joinedAt
        self.leftAt = member.leftAt
        self.status = member.status
        self.category = member.category
        self.notes = member.notes
        self.userId = member.userId
        self.createdAt = member.createdAt
        self.updatedAt = member.updatedAt
        self.cachedAt = cachedAt
    }

    /// Update all fields from a fresh API payload.
    func update(from member: Member, cachedAt: Date = .now) {
        self.memberNumber = member.memberNumber
        self.firstName = member.firstName
        self.lastName = member.lastName
        self.email = member.email
        self.phone = member.phone
        self.mobile = member.mobile
        self.birthday = member.birthday
        self.street = member.street
        self.zipCode = member.zipCode
        self.city = member.city
        self.state = member.state
        self.country = member.country
        self.joinedAt = member.joinedAt
        self.leftAt = member.leftAt
        self.status = member.status
        self.category = member.category
        self.notes = member.notes
        self.userId = member.userId
        self.createdAt = member.createdAt
        self.updatedAt = member.updatedAt
        self.cachedAt = cachedAt
    }

    func toMember() -> Member {
        Member(
            id: id,
            memberNumber: memberNumber,
            firstName: firstName,
            lastName: lastName,
            email: email,
            phone: phone,
            mobile: mobile,
            birthday: birthday,
            street: street,
            zipCode: zipCode,
            city: city,
            state: state,
            country: country,
            joinedAt: joinedAt,
            leftAt: leftAt,
            status: status,
            category: category,
            notes: notes,
            userId: userId,
            createdAt: createdAt,
            updatedAt: updatedAt
        )
    }
}
