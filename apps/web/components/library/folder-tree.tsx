"use client"

import Link from "next/link"
import { useTranslations } from "next-intl"

import { FolderDialog } from "@/components/library/folder-dialog"
import { buildFolderTree, type FolderNode } from "@/lib/library-tree"
import type { LibraryFolder } from "@/lib/types/library"
import { cn } from "@/lib/utils"
import { FolderIcon, FolderOpenIcon, InboxIcon } from "lucide-react"

/**
 * The drawers, down the left-hand side.
 *
 * Links rather than client state: which folder is open belongs in the URL, so
 * a board member can send "the 2026 minutes" to somebody else and have them
 * land in the same place.
 */
export function FolderTree({
  folders,
  currentId,
  canEdit,
}: {
  folders: LibraryFolder[]
  currentId: string | null
  canEdit: boolean
}) {
  const t = useTranslations("library")
  const tree = buildFolderTree(folders)

  return (
    <nav aria-label={t("folders")} className="space-y-1">
      <div className="flex items-center justify-between gap-2 px-2 pb-1">
        <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          {t("folders")}
        </span>
        {canEdit && <FolderDialog folders={folders} parentId={currentId} />}
      </div>

      <FolderLink
        href="/library"
        active={currentId === null}
        icon={<InboxIcon className="size-4 shrink-0" />}
        label={t("root")}
      />

      {tree.map((node) => (
        <FolderBranch
          key={node.id}
          node={node}
          currentId={currentId}
          depth={0}
        />
      ))}

      {tree.length === 0 && (
        <p className="px-2 py-1 text-xs text-muted-foreground">
          {t("noFolders")}
        </p>
      )}
    </nav>
  )
}

function FolderBranch({
  node,
  currentId,
  depth,
}: {
  node: FolderNode
  currentId: string | null
  depth: number
}) {
  const active = node.id === currentId

  return (
    <>
      <FolderLink
        href={`/library?folder=${node.id}`}
        active={active}
        depth={depth}
        icon={
          active ? (
            <FolderOpenIcon className="size-4 shrink-0" />
          ) : (
            <FolderIcon className="size-4 shrink-0" />
          )
        }
        label={node.name}
      />
      {node.children.map((child) => (
        <FolderBranch
          key={child.id}
          node={child}
          currentId={currentId}
          depth={depth + 1}
        />
      ))}
    </>
  )
}

function FolderLink({
  href,
  active,
  icon,
  label,
  depth = 0,
}: {
  href: string
  active: boolean
  icon: React.ReactNode
  label: string
  depth?: number
}) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm",
        active
          ? "bg-accent font-medium text-accent-foreground"
          : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
      )}
      // Indentation by depth rather than by nesting <ul>s: the tree is a list
      // of links, and a screen reader gets a flat list it can page through
      // instead of five nested groups.
      style={depth > 0 ? { paddingInlineStart: `${depth * 0.75 + 0.5}rem` } : undefined}
    >
      {icon}
      <span className="truncate">{label}</span>
    </Link>
  )
}
