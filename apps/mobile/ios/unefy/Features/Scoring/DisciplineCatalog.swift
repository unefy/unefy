import Foundation

/// Pre-defined discipline catalog. Each tenant can use these as suggestions.
/// Prioritized for German shooting sports (DSB, BDS).
/// Extensible: user can always type a custom discipline.
nonisolated struct Discipline: Identifiable, Hashable, Sendable {
    let id: String
    let name: String
    let category: String
    let distance: String?
    let caliber: String?

    var searchText: String {
        "\(name) \(category) \(distance ?? "") \(caliber ?? "")".lowercased()
    }
}

enum DisciplineCatalog {
    // MARK: - DSB (Deutscher Schützenbund)

    static let dsbDisciplines: [Discipline] = [
        // Luftdruckwaffen
        Discipline(id: "lg_10m", name: "Luftgewehr", category: "DSB", distance: "10m", caliber: "4.5mm"),
        Discipline(id: "lp_10m", name: "Luftpistole", category: "DSB", distance: "10m", caliber: "4.5mm"),
        Discipline(id: "lg_3x20", name: "Luftgewehr 3-Stellung", category: "DSB", distance: "10m", caliber: "4.5mm"),

        // Kleinkaliber Gewehr
        Discipline(id: "kk_50m_liegend", name: "KK Gewehr 50m liegend", category: "DSB", distance: "50m", caliber: ".22 LR"),
        Discipline(id: "kk_50m_3x40", name: "KK Gewehr 3x40", category: "DSB", distance: "50m", caliber: ".22 LR"),
        Discipline(id: "kk_100m", name: "KK Gewehr 100m", category: "DSB", distance: "100m", caliber: ".22 LR"),

        // Kleinkaliber Pistole
        Discipline(id: "kk_pistole_25m", name: "KK Sportpistole 25m", category: "DSB", distance: "25m", caliber: ".22 LR"),
        Discipline(id: "freie_pistole", name: "Freie Pistole 50m", category: "DSB", distance: "50m", caliber: ".22 LR"),
        Discipline(id: "schnellfeuerpistole", name: "Schnellfeuerpistole 25m", category: "DSB", distance: "25m", caliber: ".22 LR"),

        // Großkaliber DSB
        Discipline(id: "gk_pistole_25m", name: "GK Sportpistole 25m", category: "DSB", distance: "25m", caliber: "9mm"),
        Discipline(id: "gk_revolver_25m", name: "GK Revolver 25m", category: "DSB", distance: "25m", caliber: ".357/.38"),
    ]

    // MARK: - BDS (Bund Deutscher Sportschützen)

    static let bdsDisciplines: [Discipline] = [
        // Kurzwaffen
        Discipline(id: "bds_pistole_25m", name: "BDS Pistole 25m", category: "BDS", distance: "25m", caliber: "9mm"),
        Discipline(id: "bds_revolver_25m", name: "BDS Revolver 25m", category: "BDS", distance: "25m", caliber: ".357/.38"),
        Discipline(id: "bds_pistole_precision", name: "BDS Präzisionspistole", category: "BDS", distance: "25m", caliber: "9mm"),

        // Langwaffen
        Discipline(id: "bds_gk_gewehr_100m", name: "BDS GK Gewehr 100m", category: "BDS", distance: "100m", caliber: ".223/.308"),
        Discipline(id: "bds_kk_gewehr_50m", name: "BDS KK Gewehr 50m", category: "BDS", distance: "50m", caliber: ".22 LR"),
        Discipline(id: "bds_gk_gewehr_300m", name: "BDS GK Gewehr 300m", category: "BDS", distance: "300m", caliber: ".308"),
        Discipline(id: "bds_selbstlader_ov", name: "BDS Selbstlader offene Visierung", category: "BDS", distance: "100m", caliber: ".223/.308"),
        Discipline(id: "bds_unterhebelrep", name: "BDS Unterhebelrepetierer", category: "BDS", distance: "100m", caliber: ".357/.44"),
        Discipline(id: "bds_dienstsport_ok", name: "BDS Dienstsportgewehr offene Kimme", category: "BDS", distance: "100m", caliber: ".223/.308"),
        Discipline(id: "bds_dienstsport_diopter", name: "BDS Dienstsportgewehr Diopter", category: "BDS", distance: "100m", caliber: ".223/.308"),

        // Flinte
        Discipline(id: "bds_trap", name: "BDS Trap", category: "BDS", distance: "—", caliber: "12/20"),
        Discipline(id: "bds_skeet", name: "BDS Skeet", category: "BDS", distance: "—", caliber: "12/20"),
        Discipline(id: "bds_sporting", name: "BDS Sporting", category: "BDS", distance: "—", caliber: "12/20"),
    ]

    // MARK: - Andere Sportarten

    static let otherDisciplines: [Discipline] = [
        // Bogenschießen
        Discipline(id: "bogen_recurve_18m", name: "Recurve Halle 18m", category: "Bogenschießen", distance: "18m", caliber: nil),
        Discipline(id: "bogen_recurve_70m", name: "Recurve 70m", category: "Bogenschießen", distance: "70m", caliber: nil),
        Discipline(id: "bogen_compound_50m", name: "Compound 50m", category: "Bogenschießen", distance: "50m", caliber: nil),

        // Laufen
        Discipline(id: "lauf_5km", name: "5km Lauf", category: "Laufsport", distance: "5km", caliber: nil),
        Discipline(id: "lauf_10km", name: "10km Lauf", category: "Laufsport", distance: "10km", caliber: nil),

        // Allgemein
        Discipline(id: "custom", name: "Eigene Disziplin", category: "Sonstige", distance: nil, caliber: nil),
    ]

    static let all: [Discipline] = dsbDisciplines + bdsDisciplines + otherDisciplines

    static func search(_ query: String) -> [Discipline] {
        guard !query.isEmpty else { return all }
        let q = query.lowercased()
        return all.filter { $0.searchText.contains(q) }
    }
}
