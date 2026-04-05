"use client"

import { HugeiconsIcon } from "@hugeicons/react"
import { ColumnsThreeCogIcon } from "@hugeicons/core-free-icons"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { cn } from "@/lib/utils"

export interface ColumnSettingsColumn {
  id: string
  label: string
  canHide?: boolean
}

interface ColumnSettingsProps {
  columns: ColumnSettingsColumn[]
  columnVisibility: Record<string, boolean>
  onVisibilityChange: (state: Record<string, boolean>) => void
  triggerLabel?: string
}

export function ColumnSettings({
  columns,
  columnVisibility,
  onVisibilityChange,
  triggerLabel = "Columns",
}: ColumnSettingsProps) {
  function toggleVisibility(id: string, next: boolean) {
    onVisibilityChange({ ...columnVisibility, [id]: next })
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button variant="outline" size="sm">
            <HugeiconsIcon icon={ColumnsThreeCogIcon} size={14} />
            {triggerLabel}
          </Button>
        }
      />
      <DropdownMenuContent align="end" className="w-56 p-2">
        {columns.map((column) => {
          const canHide = column.canHide !== false
          const visible = columnVisibility[column.id] !== false
          return (
            <label
              key={column.id}
              className={cn(
                "flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm",
                canHide && "cursor-pointer hover:bg-accent",
                !canHide && "cursor-not-allowed opacity-60",
              )}
            >
              <Checkbox
                checked={visible}
                disabled={!canHide}
                onCheckedChange={(v) => canHide && toggleVisibility(column.id, v)}
              />
              <span className="flex-1">{column.label}</span>
            </label>
          )
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
