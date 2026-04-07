import SwiftUI

/// Reusable form for creating and editing members.
/// When `existingMember` is nil → create mode, otherwise → edit mode.
struct MemberFormView: View {
    let existingMember: Member?
    var onSaved: (() async -> Void)?

    @Environment(AppState.self) private var appState
    @Environment(\.dismiss) private var dismiss

    @State private var firstName = ""
    @State private var lastName = ""
    @State private var email = ""
    @State private var phone = ""
    @State private var mobile = ""
    @State private var birthday = ""
    @State private var street = ""
    @State private var zipCode = ""
    @State private var city = ""
    @State private var state_ = ""
    @State private var country = "Deutschland"
    @State private var status = "active"
    @State private var category = ""
    @State private var notes = ""

    @State private var isSaving = false
    @State private var errorMessage: String?

    private var isEditing: Bool { existingMember != nil }

    var body: some View {
        NavigationStack {
            Form {
                personalSection
                addressSection
                membershipSection
                notesSection
                if let error = errorMessage {
                    Section {
                        Text(error).foregroundStyle(.red).font(.callout)
                    }
                }
            }
            .navigationTitle(isEditing ? "members.edit" : "members.create")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("common.cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("common.save") { Task { await save() } }
                        .disabled(!canSave)
                }
            }
            .onAppear(perform: populateFromExisting)
        }
    }

    // MARK: - Sections

    private var personalSection: some View {
        Section("members.sectionPersonal") {
            TextField("members.firstName", text: $firstName)
                .textContentType(.givenName)
            TextField("members.lastName", text: $lastName)
                .textContentType(.familyName)
            TextField("members.email", text: $email)
                .keyboardType(.emailAddress)
                .textContentType(.emailAddress)
                .textInputAutocapitalization(.never)
            TextField("members.phone", text: $phone)
                .keyboardType(.phonePad)
                .textContentType(.telephoneNumber)
            TextField("members.mobile", text: $mobile)
                .keyboardType(.phonePad)
            TextField("members.birthday", text: $birthday)
                .keyboardType(.numbersAndPunctuation)
        }
    }

    private var addressSection: some View {
        Section("members.sectionAddress") {
            TextField("members.street", text: $street)
                .textContentType(.streetAddressLine1)
            TextField("members.zipCode", text: $zipCode)
                .textContentType(.postalCode)
            TextField("members.city", text: $city)
                .textContentType(.addressCity)
            TextField("members.country", text: $country)
                .textContentType(.countryName)
        }
    }

    private var membershipSection: some View {
        Section("members.sectionMembership") {
            Picker("members.status", selection: $status) {
                Text("active").tag("active")
                Text("inactive").tag("inactive")
                Text("left").tag("left")
            }
            TextField("members.category", text: $category)
        }
    }

    private var notesSection: some View {
        Section("members.sectionNotes") {
            TextEditor(text: $notes)
                .frame(minHeight: 60)
        }
    }

    // MARK: - Logic

    private var canSave: Bool {
        !isSaving
            && !firstName.trimmingCharacters(in: .whitespaces).isEmpty
            && !lastName.trimmingCharacters(in: .whitespaces).isEmpty
    }

    private func populateFromExisting() {
        guard let m = existingMember else { return }
        firstName = m.firstName
        lastName = m.lastName
        email = m.email ?? ""
        phone = m.phone ?? ""
        mobile = m.mobile ?? ""
        birthday = m.birthday ?? ""
        street = m.street ?? ""
        zipCode = m.zipCode ?? ""
        city = m.city ?? ""
        state_ = m.state ?? ""
        country = m.country ?? "Deutschland"
        status = m.status
        category = m.category ?? ""
        notes = m.notes ?? ""
    }

    private func save() async {
        isSaving = true
        errorMessage = nil
        defer { isSaving = false }

        do {
            if let existing = existingMember {
                try await update(existing)
            } else {
                try await create()
            }
            dismiss()
            await onSaved?()
        } catch let error as APIError {
            errorMessage = ErrorMessageMapper.message(for: error)
        } catch {
            errorMessage = String(localized: "errors.unknown")
        }
    }

    private func create() async throws {
        let payload = MemberCreatePayload(
            firstName: firstName.trimmed,
            lastName: lastName.trimmed,
            email: email.nilIfEmpty,
            phone: phone.nilIfEmpty,
            mobile: mobile.nilIfEmpty,
            birthday: birthday.nilIfEmpty,
            street: street.nilIfEmpty,
            zipCode: zipCode.nilIfEmpty,
            city: city.nilIfEmpty,
            state: state_.nilIfEmpty,
            country: country.nilIfEmpty,
            joinedAt: nil,
            status: status,
            category: category.nilIfEmpty,
            notes: notes.nilIfEmpty
        )
        let _: Member = try await appState.apiClient.request(.createMember(payload))
    }

    private func update(_ existing: Member) async throws {
        let payload = MemberUpdatePayload(
            firstName: firstName.trimmed,
            lastName: lastName.trimmed,
            email: email.nilIfEmpty,
            phone: phone.nilIfEmpty,
            mobile: mobile.nilIfEmpty,
            birthday: birthday.nilIfEmpty,
            street: street.nilIfEmpty,
            zipCode: zipCode.nilIfEmpty,
            city: city.nilIfEmpty,
            state: state_.nilIfEmpty,
            country: country.nilIfEmpty,
            joinedAt: nil,
            status: status,
            category: category.nilIfEmpty,
            notes: notes.nilIfEmpty
        )
        let _: Member = try await appState.apiClient.request(
            .updateMember(id: existing.id, data: payload)
        )
    }
}

private extension String {
    var trimmed: String { trimmingCharacters(in: .whitespaces) }
    var nilIfEmpty: String? {
        let t = trimmed
        return t.isEmpty ? nil : t
    }
}
