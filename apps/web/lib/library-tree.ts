import type { LibraryFolder } from "@/lib/types/library"

/**
 * Turning the flat folder list into a tree, and back into a path.
 *
 * Pure on purpose, and in its own file: the backend sends folders flat (a
 * club's list is small), so every one of these questions — what hangs under
 * this drawer, where am I, what can this folder be moved into — is answered
 * here rather than three times over in three components. It is also the part
 * that can go quietly wrong: a folder whose parent is missing must not vanish
 * from the tree, and a cycle must not hang the browser.
 */

export type FolderNode = LibraryFolder & { children: FolderNode[] }

/** Folders in one drawer: by `sort_order`, then by name. */
function byOrder(a: LibraryFolder, b: LibraryFolder): number {
  return a.sort_order - b.sort_order || a.name.localeCompare(b.name, "de")
}

/**
 * The tree, roots first.
 *
 * A folder whose parent is not in the list is treated as a root rather than
 * dropped. That should not happen — the backend sends the whole tree — but a
 * folder the user cannot find is worse than one shown a level too high.
 */
export function buildFolderTree(folders: LibraryFolder[]): FolderNode[] {
  const nodes = new Map<string, FolderNode>(
    folders.map((folder) => [folder.id, { ...folder, children: [] }])
  )
  const roots: FolderNode[] = []

  for (const node of nodes.values()) {
    const parent = node.parent_id ? nodes.get(node.parent_id) : undefined
    if (parent && parent.id !== node.id) parent.children.push(node)
    else roots.push(node)
  }

  const sort = (list: FolderNode[]) => {
    list.sort(byOrder)
    list.forEach((node) => sort(node.children))
  }
  sort(roots)
  return roots
}

/**
 * The breadcrumb for a folder: root first, the folder itself last.
 *
 * The visited set is not decoration. The backend refuses to create a cycle,
 * but this walk runs in the browser over data it was handed, and a loop here
 * would freeze the tab rather than show a wrong path.
 */
export function folderPath(
  folders: LibraryFolder[],
  folderId: string | null
): LibraryFolder[] {
  const byId = new Map(folders.map((folder) => [folder.id, folder]))
  const path: LibraryFolder[] = []
  const seen = new Set<string>()

  let current = folderId ? byId.get(folderId) : undefined
  while (current && !seen.has(current.id)) {
    seen.add(current.id)
    path.unshift(current)
    current = current.parent_id ? byId.get(current.parent_id) : undefined
  }
  return path
}

/**
 * Every folder below this one, itself included.
 *
 * Used to grey out the impossible choices when moving a folder: the backend
 * refuses to move a drawer into its own subtree, and offering it anyway means
 * an error message where a disabled option would do.
 */
export function descendantIds(
  folders: LibraryFolder[],
  folderId: string
): Set<string> {
  const children = new Map<string, string[]>()
  for (const folder of folders) {
    if (!folder.parent_id) continue
    const siblings = children.get(folder.parent_id) ?? []
    siblings.push(folder.id)
    children.set(folder.parent_id, siblings)
  }

  const found = new Set<string>([folderId])
  const queue = [folderId]
  while (queue.length > 0) {
    const id = queue.shift() as string
    for (const child of children.get(id) ?? []) {
      if (found.has(child)) continue
      found.add(child)
      queue.push(child)
    }
  }
  return found
}

/** Folders as a flat list of "Protokolle ▸ 2026" labels, for a Select. */
export function folderOptions(
  folders: LibraryFolder[]
): { id: string; label: string }[] {
  const walk = (nodes: FolderNode[], prefix: string): { id: string; label: string }[] =>
    nodes.flatMap((node) => {
      const label = prefix ? `${prefix} ▸ ${node.name}` : node.name
      return [{ id: node.id, label }, ...walk(node.children, label)]
    })
  return walk(buildFolderTree(folders), "")
}

const UNITS = ["B", "KB", "MB", "GB"] as const

/**
 * A file size someone can read at a glance.
 *
 * Powers of 1024 with the short unit names, which is what every file manager
 * on a club's computer shows. Rounded to one decimal from a megabyte up —
 * "3,4 MB" is the useful answer, "3.421.184 B" is not.
 */
export function formatBytes(bytes: number, locale = "de"): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "—"
  let value = bytes
  let unit = 0
  while (value >= 1024 && unit < UNITS.length - 1) {
    value /= 1024
    unit += 1
  }
  const digits = unit >= 2 && value < 100 ? 1 : 0
  return `${value.toLocaleString(locale, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })} ${UNITS[unit]}`
}
