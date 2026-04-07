import SwiftUI

struct MemberDetailView: View {
    let member: Member
    @State private var showEditSheet = false

    var body: some View {
        Form {
            Section("members.sectionPersonal") {
                LabeledContent("members.name", value: member.fullName)
                LabeledContent("members.memberNumber", value: member.memberNumber)
                if let email = member.email, !email.isEmpty {
                    ContactLink(
                        label: String(localized: "members.email"),
                        value: email,
                        url: URL(string: "mailto:\(email)")
                    )
                }
                if let phone = member.phone, !phone.isEmpty {
                    ContactLink(
                        label: String(localized: "members.phone"),
                        value: phone,
                        url: URL(string: "tel:\(phone.telURL)")
                    )
                }
                if let mobile = member.mobile, !mobile.isEmpty {
                    ContactLink(
                        label: String(localized: "members.mobile"),
                        value: mobile,
                        url: URL(string: "tel:\(mobile.telURL)")
                    )
                }
                if let birthday = DateFormatting.displayDate(member.birthday) {
                    LabeledContent("members.birthday", value: birthday)
                }
            }

            if hasAddress {
                Section("members.sectionAddress") {
                    if let street = member.street, !street.isEmpty {
                        LabeledContent("members.street", value: street)
                    }
                    let locality = [member.zipCode, member.city]
                        .compactMap { $0 }
                        .filter { !$0.isEmpty }
                        .joined(separator: " ")
                    if !locality.isEmpty {
                        LabeledContent("members.city", value: locality)
                    }
                    if let country = member.country, !country.isEmpty {
                        LabeledContent("members.country", value: country)
                    }
                }
            }

            Section("members.sectionMembership") {
                if let joined = DateFormatting.displayDate(member.joinedAt) {
                    LabeledContent("members.joinedAt", value: joined)
                }
                if let leftAt = DateFormatting.displayDate(member.leftAt) {
                    LabeledContent("members.leftAt", value: leftAt)
                }
                LabeledContent("members.status", value: member.status)
                if let category = member.category, !category.isEmpty {
                    LabeledContent("members.category", value: category)
                }
            }

            if let notes = member.notes, !notes.isEmpty {
                Section("members.sectionNotes") {
                    Text(notes)
                }
            }
        }
        .navigationTitle(member.fullName)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button {
                    showEditSheet = true
                } label: {
                    Text("members.edit")
                }
            }
        }
        .sheet(isPresented: $showEditSheet) {
            MemberFormView(existingMember: member)
        }
    }

    private var hasAddress: Bool {
        !(member.street ?? "").isEmpty
            || !(member.city ?? "").isEmpty
            || !(member.country ?? "").isEmpty
            || !(member.zipCode ?? "").isEmpty
    }
}

private struct ContactLink: View {
    let label: String
    let value: String
    let url: URL?

    var body: some View {
        if let url {
            Link(destination: url) {
                LabeledContent(label) {
                    Text(value)
                        .foregroundStyle(.tint)
                }
            }
            .buttonStyle(.plain)
        } else {
            LabeledContent(label, value: value)
        }
    }
}

private extension String {
    /// Strip whitespace for use in a `tel:` URL.
    var telURL: String {
        replacingOccurrences(of: " ", with: "")
            .replacingOccurrences(of: "/", with: "")
            .replacingOccurrences(of: "-", with: "")
    }
}
