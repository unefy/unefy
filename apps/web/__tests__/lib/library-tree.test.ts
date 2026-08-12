import { describe, expect, it } from "vitest"

import {
  buildFolderTree,
  descendantIds,
  folderOptions,
  folderPath,
  formatBytes,
} from "@/lib/library-tree"
import type { LibraryFolder } from "@/lib/types/library"

function folder(
  id: string,
  name: string,
  parent_id: string | null = null,
  sort_order = 0
): LibraryFolder {
  return {
    id,
    name,
    parent_id,
    sort_order,
    created_at: "2026-08-12T10:00:00Z",
    updated_at: "2026-08-12T10:00:00Z",
  }
}

const TREE = [
  folder("a", "Protokolle"),
  folder("b", "2026", "a"),
  folder("c", "Q1", "b"),
  folder("d", "Finanzen", null, 1),
]

describe("buildFolderTree", () => {
  it("hangs each folder under its parent", () => {
    const roots = buildFolderTree(TREE)

    expect(roots.map((node) => node.name)).toEqual(["Protokolle", "Finanzen"])
    expect(roots[0].children[0].name).toBe("2026")
    expect(roots[0].children[0].children[0].name).toBe("Q1")
  })

  it("sorts by sort_order first and by name after", () => {
    const roots = buildFolderTree([
      folder("x", "Zuletzt", null, 0),
      folder("y", "Anfang", null, 0),
      folder("z", "Vorne", null, -1),
    ])

    expect(roots.map((node) => node.name)).toEqual([
      "Vorne",
      "Anfang",
      "Zuletzt",
    ])
  })

  it("shows a folder whose parent is missing rather than losing it", () => {
    // Should not happen — the backend sends the whole tree. A folder nobody
    // can find would be worse than one shown a level too high.
    const roots = buildFolderTree([folder("orphan", "Verwaist", "gone")])

    expect(roots.map((node) => node.name)).toEqual(["Verwaist"])
  })

  it("does not hang on a folder that is its own parent", () => {
    const roots = buildFolderTree([folder("self", "Selbst", "self")])

    expect(roots).toHaveLength(1)
  })

  it("leaves the input alone", () => {
    const input = [folder("a", "Protokolle"), folder("b", "2026", "a")]
    buildFolderTree(input)

    expect(input[0]).not.toHaveProperty("children")
  })
})

describe("folderPath", () => {
  it("reads from the root down to the folder itself", () => {
    expect(folderPath(TREE, "c").map((f) => f.name)).toEqual([
      "Protokolle",
      "2026",
      "Q1",
    ])
  })

  it("is empty at the root", () => {
    expect(folderPath(TREE, null)).toEqual([])
  })

  it("is empty for a folder that is not in the list", () => {
    expect(folderPath(TREE, "nope")).toEqual([])
  })

  it("stops instead of looping forever on a cycle", () => {
    // The backend refuses to create one, but this walk runs in the browser
    // over data it was handed — a loop here freezes the tab.
    const cyclic = [folder("a", "A", "b"), folder("b", "B", "a")]

    expect(folderPath(cyclic, "a").map((f) => f.name)).toEqual(["B", "A"])
  })
})

describe("descendantIds", () => {
  it("includes the folder itself and everything under it", () => {
    expect([...descendantIds(TREE, "a")].sort()).toEqual(["a", "b", "c"])
  })

  it("is just the folder when it has no children", () => {
    expect([...descendantIds(TREE, "d")]).toEqual(["d"])
  })

  it("terminates on a cycle", () => {
    const cyclic = [folder("a", "A", "b"), folder("b", "B", "a")]

    expect([...descendantIds(cyclic, "a")].sort()).toEqual(["a", "b"])
  })
})

describe("folderOptions", () => {
  it("labels each folder with its path", () => {
    expect(folderOptions(TREE)).toEqual([
      { id: "a", label: "Protokolle" },
      { id: "b", label: "Protokolle ▸ 2026" },
      { id: "c", label: "Protokolle ▸ 2026 ▸ Q1" },
      { id: "d", label: "Finanzen" },
    ])
  })
})

describe("formatBytes", () => {
  it("uses the unit a file manager would use", () => {
    expect(formatBytes(0, "de")).toBe("0 B")
    expect(formatBytes(999, "de")).toBe("999 B")
    expect(formatBytes(1024, "de")).toBe("1 KB")
    expect(formatBytes(1536, "de")).toBe("2 KB")
  })

  it("shows one decimal from a megabyte up, where it matters", () => {
    expect(formatBytes(3.4 * 1024 * 1024, "de")).toBe("3,4 MB")
    expect(formatBytes(1024 * 1024 * 1024, "de")).toBe("1,0 GB")
  })

  it("drops the decimal again once the number is long", () => {
    expect(formatBytes(524 * 1024 * 1024, "de")).toBe("524 MB")
  })

  it("follows the locale's decimal mark", () => {
    expect(formatBytes(3.4 * 1024 * 1024, "en")).toBe("3.4 MB")
  })

  it("says nothing rather than something wrong", () => {
    expect(formatBytes(-1, "de")).toBe("—")
    expect(formatBytes(Number.NaN, "de")).toBe("—")
  })
})
