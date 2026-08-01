import { describe, expect, it } from "vitest"

import {
  ALL,
  applySearch,
  applySort,
  compare,
  computeRows,
  filterValue,
  isEmpty,
  nextSort,
  type DataTableColumn,
  type DataTableFilter,
} from "@/lib/data-table"

type Row = {
  id: string
  name: string
  city: string | null
  count: number
  active: boolean
  status: string
}

const ROWS: Row[] = [
  {
    id: "1",
    name: "Zimmermann",
    city: "Ulm",
    count: 3,
    active: true,
    status: "active",
  },
  {
    id: "2",
    name: "Ärztin",
    city: null,
    count: 25,
    active: false,
    status: "inactive",
  },
  {
    id: "3",
    name: "Bauer",
    city: "Ulm",
    count: 1,
    active: true,
    status: "active",
  },
  {
    id: "4",
    name: "möller",
    city: "Aalen",
    count: 10,
    active: false,
    status: "resigned",
  },
]

const columns: DataTableColumn<Row>[] = [
  {
    key: "name",
    header: "Name",
    cell: (r) => r.name,
    sortValue: (r) => r.name,
  },
  { key: "city", header: "Ort", cell: (r) => r.city, sortValue: (r) => r.city },
  {
    key: "count",
    header: "Anzahl",
    cell: (r) => r.count,
    sortValue: (r) => r.count,
  },
  {
    key: "active",
    header: "Aktiv",
    cell: (r) => r.active,
    sortValue: (r) => r.active,
  },
  // Deliberately without sortValue — must stay unsortable.
  { key: "plain", header: "Nur Anzeige", cell: (r) => r.id },
]

const names = (rows: Row[]) => rows.map((r) => r.name)

describe("isEmpty", () => {
  it.each([null, undefined, ""])("treats %s as empty", (value) => {
    expect(isEmpty(value)).toBe(true)
  })

  it.each([0, false, "x"])("does not treat %s as empty", (value) => {
    // `0` and `false` are real values — dropping them to the bottom of a sort
    // would misrepresent a club with zero members.
    expect(isEmpty(value)).toBe(false)
  })
})

describe("compare", () => {
  it("compares numbers numerically, not as text", () => {
    // String comparison would put 10 before 3.
    expect(compare(3, 10, "de")).toBeLessThan(0)
  })

  it("sorts false before true", () => {
    expect(compare(false, true, "de")).toBeLessThan(0)
  })

  it("uses locale collation for umlauts", () => {
    // "Ärztin" belongs next to A, not after Z as a byte comparison would have it.
    expect(compare("Ärztin", "Bauer", "de")).toBeLessThan(0)
  })

  it("does not let case outweigh letter order", () => {
    // Case only breaks ties between otherwise identical strings; a byte
    // comparison would sort every capital ahead of every lowercase letter,
    // scattering "möller" and "Nachbar" into the wrong halves of the list.
    expect(compare("möller", "Nachbar", "de")).toBeLessThan(0)
    expect(compare("Möller", "nachbar", "de")).toBeLessThan(0)
  })
})

describe("applySort", () => {
  it("sorts ascending by string", () => {
    const sorted = applySort(
      ROWS,
      columns,
      { key: "name", direction: "asc" },
      "de"
    )
    expect(names(sorted)).toEqual(["Ärztin", "Bauer", "möller", "Zimmermann"])
  })

  it("reverses on descending", () => {
    const sorted = applySort(
      ROWS,
      columns,
      { key: "name", direction: "desc" },
      "de"
    )
    expect(names(sorted)).toEqual(["Zimmermann", "möller", "Bauer", "Ärztin"])
  })

  it("keeps empty values last in both directions", () => {
    // Otherwise a descending sort leads with a column of dashes.
    const asc = applySort(
      ROWS,
      columns,
      { key: "city", direction: "asc" },
      "de"
    )
    const desc = applySort(
      ROWS,
      columns,
      { key: "city", direction: "desc" },
      "de"
    )

    expect(asc.at(-1)?.city).toBeNull()
    expect(desc.at(-1)?.city).toBeNull()
  })

  it("sorts numbers by value", () => {
    const sorted = applySort(
      ROWS,
      columns,
      { key: "count", direction: "asc" },
      "de"
    )
    expect(sorted.map((r) => r.count)).toEqual([1, 3, 10, 25])
  })

  it("leaves the order untouched for a column without sortValue", () => {
    const sorted = applySort(
      ROWS,
      columns,
      { key: "plain", direction: "asc" },
      "de"
    )
    expect(names(sorted)).toEqual(names(ROWS))
  })

  it("leaves the order untouched for an unknown column", () => {
    const sorted = applySort(
      ROWS,
      columns,
      { key: "nope", direction: "asc" },
      "de"
    )
    expect(names(sorted)).toEqual(names(ROWS))
  })

  it("does not mutate the input array", () => {
    const before = names(ROWS)
    applySort(ROWS, columns, { key: "name", direction: "desc" }, "de")
    expect(names(ROWS)).toEqual(before)
  })
})

describe("applySearch", () => {
  const fields = (row: Row) => [row.name, row.city]

  it("matches case-insensitively on a substring", () => {
    expect(names(applySearch(ROWS, "AUE", fields))).toEqual(["Bauer"])
  })

  it("searches across every listed field", () => {
    expect(names(applySearch(ROWS, "ulm", fields))).toEqual([
      "Zimmermann",
      "Bauer",
    ])
  })

  it("survives null fields", () => {
    // A member without a city must not blow up the search.
    expect(() => applySearch(ROWS, "x", fields)).not.toThrow()
  })

  it("returns everything for a blank needle", () => {
    expect(applySearch(ROWS, "   ", fields)).toHaveLength(ROWS.length)
  })

  it("returns everything when no search fields are configured", () => {
    expect(applySearch(ROWS, "bauer", undefined)).toHaveLength(ROWS.length)
  })
})

describe("filters", () => {
  const statusFilter: DataTableFilter<Row> = {
    key: "status",
    allLabel: "Alle",
    options: [{ value: "active", label: "Aktiv" }],
    matches: (row, value) => row.status === value,
  }

  it("filters on the chosen value", () => {
    const rows = computeRows({
      data: ROWS,
      columns,
      filters: [statusFilter],
      filterValues: { status: "active" },
      search: "",
      sort: null,
      locale: "de",
    })
    expect(names(rows)).toEqual(["Zimmermann", "Bauer"])
  })

  it("returns everything for the ALL sentinel", () => {
    const rows = computeRows({
      data: ROWS,
      columns,
      filters: [statusFilter],
      filterValues: { status: ALL },
      search: "",
      sort: null,
      locale: "de",
    })
    expect(rows).toHaveLength(ROWS.length)
  })

  it("ignores a controlled filter — the page already applied it", () => {
    /**
     * A server-side filter has no `matches`. Filtering again here would remove
     * rows a second time and silently hide data the server deliberately sent.
     */
    const controlled: DataTableFilter<Row> = {
      key: "status",
      allLabel: "Alle",
      options: [{ value: "active", label: "Aktiv" }],
      value: "active",
      onValueChange: () => {},
    }
    const rows = computeRows({
      data: ROWS,
      columns,
      filters: [controlled],
      filterValues: {},
      search: "",
      sort: null,
      locale: "de",
    })
    expect(rows).toHaveLength(ROWS.length)
  })

  it("reads a controlled filter's value from the filter, not from local state", () => {
    const controlled: DataTableFilter<Row> = {
      key: "status",
      allLabel: "Alle",
      options: [],
      value: "resigned",
      onValueChange: () => {},
    }
    expect(filterValue(controlled, { status: "active" })).toBe("resigned")
    expect(filterValue(statusFilter, { status: "active" })).toBe("active")
    expect(filterValue(statusFilter, {})).toBe(ALL)
  })
})

describe("computeRows", () => {
  it("applies filter, search and sort together", () => {
    const rows = computeRows({
      data: ROWS,
      columns,
      filters: [
        {
          key: "status",
          allLabel: "Alle",
          options: [],
          matches: (row, value) => row.status === value,
        },
      ],
      filterValues: { status: "active" },
      search: "ulm",
      searchFields: (row) => [row.name, row.city],
      sort: { key: "name", direction: "asc" },
      locale: "de",
    })

    expect(names(rows)).toEqual(["Bauer", "Zimmermann"])
  })
})

describe("nextSort", () => {
  it("starts a new column ascending", () => {
    expect(nextSort(null, "name")).toEqual({ key: "name", direction: "asc" })
    expect(nextSort({ key: "city", direction: "desc" }, "name")).toEqual({
      key: "name",
      direction: "asc",
    })
  })

  it("flips direction on the same column", () => {
    expect(nextSort({ key: "name", direction: "asc" }, "name")).toEqual({
      key: "name",
      direction: "desc",
    })
    expect(nextSort({ key: "name", direction: "desc" }, "name")).toEqual({
      key: "name",
      direction: "asc",
    })
  })
})
