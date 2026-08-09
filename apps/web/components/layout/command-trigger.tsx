"use client"

import { useSyncExternalStore } from "react"
import { useTranslations } from "next-intl"

import { Button } from "@/components/ui/button"
import { SearchIcon } from "lucide-react"

/**
 * The visible half of the command palette.
 *
 * A shortcut nobody is told about does not exist, so the header carries the
 * hint. Clicking it dispatches the same key the palette listens for, which
 * keeps the open logic in one place instead of lifting state through the
 * server-rendered layout.
 */
/** The platform never changes while the page is open — nothing to subscribe to. */
const NO_CHANGES = () => () => {}

export function CommandTrigger() {
  const t = useTranslations("commandPalette")

  // Read on the client only: the server does not know which keyboard is out
  // there, and rendering ⌘ into the HTML would hydrate wrong on Windows.
  const isMac = useSyncExternalStore(
    NO_CHANGES,
    () => /Mac|iPhone|iPad/.test(navigator.platform),
    () => false
  )

  return (
    <Button
      variant="outline"
      size="sm"
      className="text-muted-foreground"
      onClick={() =>
        document.dispatchEvent(
          new KeyboardEvent("keydown", { key: "k", metaKey: true })
        )
      }
    >
      <SearchIcon />
      <span className="max-sm:sr-only">{t("trigger")}</span>
      <kbd className="ms-1 rounded border bg-muted px-1.5 py-0.5 font-mono text-[10px] max-sm:hidden">
        {isMac ? "⌘" : "Ctrl "}K
      </kbd>
    </Button>
  )
}
