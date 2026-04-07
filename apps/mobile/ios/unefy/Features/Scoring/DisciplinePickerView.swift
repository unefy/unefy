import SwiftUI

/// Searchable discipline picker. Shows catalog grouped by category,
/// with search. User can also type a custom discipline.
struct DisciplinePickerView: View {
    @Binding var selected: String
    @Environment(\.dismiss) private var dismiss
    @State private var searchText = ""

    private var results: [String: [Discipline]] {
        let filtered = DisciplineCatalog.search(searchText)
        return Dictionary(grouping: filtered, by: { $0.category })
    }

    private var sortedCategories: [String] {
        let order = ["DSB", "BDS", "Bogenschießen", "Laufsport", "Sonstige"]
        return results.keys.sorted { a, b in
            let ia = order.firstIndex(of: a) ?? 99
            let ib = order.firstIndex(of: b) ?? 99
            return ia < ib
        }
    }

    var body: some View {
        NavigationStack {
            List {
                // Custom entry if search doesn't match anything exactly
                if !searchText.isEmpty && !DisciplineCatalog.all.contains(where: { $0.name.lowercased() == searchText.lowercased() }) {
                    Section {
                        Button {
                            selected = searchText
                            dismiss()
                        } label: {
                            Label("\"\(searchText)\" verwenden", systemImage: "plus.circle")
                        }
                    }
                }

                ForEach(sortedCategories, id: \.self) { category in
                    Section(category) {
                        ForEach(results[category] ?? []) { discipline in
                            Button {
                                selected = discipline.name
                                dismiss()
                            } label: {
                                HStack {
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(discipline.name)
                                            .foregroundStyle(.primary)
                                        if let dist = discipline.distance, let cal = discipline.caliber {
                                            Text("\(dist) · \(cal)")
                                                .font(.caption)
                                                .foregroundStyle(.secondary)
                                        } else if let dist = discipline.distance {
                                            Text(dist)
                                                .font(.caption)
                                                .foregroundStyle(.secondary)
                                        }
                                    }
                                    Spacer()
                                    if discipline.name == selected {
                                        Image(systemName: "checkmark")
                                            .foregroundStyle(.blue)
                                    }
                                }
                            }
                        }
                    }
                }
            }
            .searchable(text: $searchText, prompt: "events.searchDiscipline")
            .navigationTitle("events.selectDiscipline")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("common.cancel") { dismiss() }
                }
            }
        }
    }
}
