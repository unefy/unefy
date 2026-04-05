"use client"

import * as React from "react"
import {
  type ColumnDef,
  type ColumnOrderState,
  type Header,
  type Row,
  type RowData,
  type RowSelectionState,
  type SortingState,
  type VisibilityState,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table"
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragMoveEvent,
  type DragStartEvent,
} from "@dnd-kit/core"
import {
  arrayMove,
  horizontalListSortingStrategy,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
} from "@dnd-kit/sortable"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  ArrowDown01Icon,
  ArrowUp01Icon,
  ArrowDataTransferHorizontalIcon,
} from "@hugeicons/core-free-icons"

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { cn } from "@/lib/utils"

declare module "@tanstack/react-table" {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  interface ColumnMeta<TData extends RowData, TValue> {
    /** Extra className applied to the TableHead cell. */
    headerClassName?: string
    /** Extra className applied to every body TableCell in this column. */
    cellClassName?: string
    /** Backend sort field identifier (for server-side sorting). */
    sortField?: string
  }
}

interface DataTableProps<TData> {
  columns: ColumnDef<TData, unknown>[]
  data: TData[]
  isLoading?: boolean
  error?: Error | null
  emptyState?: React.ReactNode
  errorState?: React.ReactNode
  emptyStateText?: string
  errorStateText?: string
  skeletonRows?: number
  rowSelection?: RowSelectionState
  onRowSelectionChange?: (state: RowSelectionState) => void
  sorting?: SortingState
  onSortingChange?: (state: SortingState) => void
  columnVisibility?: VisibilityState
  onColumnVisibilityChange?: (state: VisibilityState) => void
  columnOrder?: ColumnOrderState
  onColumnOrderChange?: (state: ColumnOrderState) => void
  /**
   * Column IDs that cannot be reordered via drag (e.g. "select").
   * They are rendered but the drag handle is disabled.
   */
  lockedColumnIds?: string[]
  getRowId?: (row: TData, index: number, parent?: Row<TData>) => string
  onRowClick?: (row: TData) => void
  isRowSelected?: (row: TData) => boolean
}

function ariaSortFor(
  dir: false | "asc" | "desc",
): "ascending" | "descending" | "none" {
  if (dir === "asc") return "ascending"
  if (dir === "desc") return "descending"
  return "none"
}

function DraggableHeader<TData>({
  header,
  locked,
  onTransformChange,
}: {
  header: Header<TData, unknown>
  locked: boolean
  onTransformChange: (id: string, x: number, transition: string | undefined) => void
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: header.column.id, disabled: locked })

  const canSort = header.column.getCanSort()
  const sorted = header.column.getIsSorted()
  const width = header.getSize()

  // Propagate the per-column horizontal transform so body cells of the same
  // column can mirror it (including cells of columns being displaced).
  const transformX = transform?.x ?? 0
  const columnId = header.column.id
  React.useEffect(() => {
    onTransformChange(columnId, transformX, transition)
  }, [columnId, transformX, transition, onTransformChange])

  const style: React.CSSProperties = {
    width: width ? `${width}px` : undefined,
    // Strip Y axis so the header only moves horizontally — prevents the cell
    // from overflowing the table vertically and triggering scrollbars.
    transform: transform
      ? `translate3d(${transform.x}px, 0, 0)`
      : undefined,
    transition,
    zIndex: isDragging ? 1 : undefined,
    position: isDragging ? "relative" : undefined,
  }

  return (
    <TableHead
      ref={setNodeRef}
      style={style}
      aria-sort={canSort ? ariaSortFor(sorted) : undefined}
      className={cn(
        header.column.columnDef.meta?.headerClassName,
        !locked && "cursor-grab touch-none select-none active:cursor-grabbing",
        isDragging && "bg-accent/60",
      )}
      {...(!locked ? attributes : {})}
      {...(!locked ? listeners : {})}
    >
      {header.isPlaceholder ? null : canSort ? (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            header.column.getToggleSortingHandler()?.(e)
          }}
          className="flex items-center gap-1.5 hover:text-foreground transition-colors"
        >
          {flexRender(header.column.columnDef.header, header.getContext())}
          <HugeiconsIcon
            icon={
              sorted === "asc"
                ? ArrowUp01Icon
                : sorted === "desc"
                  ? ArrowDown01Icon
                  : ArrowDataTransferHorizontalIcon
            }
            size={12}
            className={cn(
              "shrink-0 transition-opacity",
              sorted ? "opacity-100" : "opacity-40",
            )}
          />
        </button>
      ) : (
        flexRender(header.column.columnDef.header, header.getContext())
      )}
    </TableHead>
  )
}

export function DataTable<TData>({
  columns,
  data,
  isLoading,
  error,
  emptyState,
  errorState,
  emptyStateText = "No data",
  errorStateText = "Could not load data",
  skeletonRows = 8,
  rowSelection,
  onRowSelectionChange,
  sorting,
  onSortingChange,
  columnVisibility,
  onColumnVisibilityChange,
  columnOrder,
  onColumnOrderChange,
  lockedColumnIds = [],
  getRowId,
  onRowClick,
  isRowSelected,
}: DataTableProps<TData>) {
  const table = useReactTable({
    data,
    columns,
    state: {
      rowSelection: rowSelection ?? {},
      sorting: sorting ?? [],
      columnVisibility: columnVisibility ?? {},
      columnOrder: columnOrder ?? [],
    },
    onRowSelectionChange: (updater) => {
      if (!onRowSelectionChange) return
      const next =
        typeof updater === "function" ? updater(rowSelection ?? {}) : updater
      onRowSelectionChange(next)
    },
    onSortingChange: (updater) => {
      if (!onSortingChange) return
      const next =
        typeof updater === "function" ? updater(sorting ?? []) : updater
      onSortingChange(next)
    },
    onColumnVisibilityChange: (updater) => {
      if (!onColumnVisibilityChange) return
      const next =
        typeof updater === "function"
          ? updater(columnVisibility ?? {})
          : updater
      onColumnVisibilityChange(next)
    },
    onColumnOrderChange: (updater) => {
      if (!onColumnOrderChange) return
      const next =
        typeof updater === "function" ? updater(columnOrder ?? []) : updater
      onColumnOrderChange(next)
    },
    getRowId,
    enableRowSelection: !!onRowSelectionChange,
    manualPagination: true,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  const sensors = useSensors(
    // 6px distance so click-to-sort still fires; past 6px movement = drag
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  // @dnd-kit generates internal IDs that can mismatch during SSR hydration.
  // Enable drag only after client mount.
  const [dndReady, setDndReady] = React.useState(false)
  React.useEffect(() => {
    setDndReady(true)
  }, [])

  const [draggedColumnId, setDraggedColumnId] = React.useState<string | null>(
    null,
  )
  const [dragOffsetX, setDragOffsetX] = React.useState(0)
  const [columnTransforms, setColumnTransforms] = React.useState<
    Record<string, { x: number; transition: string | undefined }>
  >({})

  const handleColumnTransform = React.useCallback(
    (id: string, x: number, transition: string | undefined) => {
      setColumnTransforms((prev) => {
        const current = prev[id]
        if (current && current.x === x && current.transition === transition) {
          return prev
        }
        return { ...prev, [id]: { x, transition } }
      })
    },
    [],
  )

  const headerGroups = table.getHeaderGroups()
  const visibleLeafColumnsCount = table.getVisibleLeafColumns().length
  const visibleColumnIds = React.useMemo(
    () => table.getVisibleLeafColumns().map((c) => c.id),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [columnOrder, columnVisibility, columns, visibleLeafColumnsCount],
  )

  function handleDragStart(event: DragStartEvent) {
    setDraggedColumnId(String(event.active.id))
    setDragOffsetX(0)
  }

  function handleDragMove(event: DragMoveEvent) {
    setDragOffsetX(event.delta.x)
  }

  function handleDragEnd(event: DragEndEvent) {
    setDraggedColumnId(null)
    setDragOffsetX(0)
    const { active, over } = event
    if (!over || active.id === over.id || !onColumnOrderChange) return
    const oldIndex = visibleColumnIds.indexOf(String(active.id))
    const newIndex = visibleColumnIds.indexOf(String(over.id))
    if (oldIndex < 0 || newIndex < 0) return
    onColumnOrderChange(arrayMove(visibleColumnIds, oldIndex, newIndex))
  }

  function handleDragCancel() {
    setDraggedColumnId(null)
    setDragOffsetX(0)
  }

  const dragEnabled = dndReady && !!onColumnOrderChange
  const colSpan = table.getVisibleLeafColumns().length

  function renderStateRow(content: React.ReactNode) {
    return (
      <TableRow>
        <TableCell colSpan={colSpan} className="h-40 text-center">
          {content}
        </TableCell>
      </TableRow>
    )
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragStart={handleDragStart}
      onDragMove={handleDragMove}
      onDragEnd={handleDragEnd}
      onDragCancel={handleDragCancel}
    >
      <Table className="table-fixed">
        <TableHeader>
          {headerGroups.map((headerGroup) => (
            <TableRow key={headerGroup.id}>
              <SortableContext
                items={visibleColumnIds}
                strategy={horizontalListSortingStrategy}
              >
                {headerGroup.headers.map((header) => (
                  <DraggableHeader
                    key={header.id}
                    header={header}
                    locked={
                      !dragEnabled ||
                      lockedColumnIds.includes(header.column.id)
                    }
                    onTransformChange={handleColumnTransform}
                  />
                ))}
              </SortableContext>
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {isLoading
            ? Array.from({ length: skeletonRows }).map((_, i) => (
                <TableRow key={`skeleton-${i}`}>
                  {table.getVisibleLeafColumns().map((col) => (
                    <TableCell key={col.id}>
                      <div className="h-4 bg-muted animate-pulse rounded" />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            : error
              ? renderStateRow(
                  errorState ?? (
                    <span className="text-destructive text-sm">
                      {errorStateText}
                    </span>
                  ),
                )
              : table.getRowModel().rows.length === 0
                ? renderStateRow(
                    emptyState ?? (
                      <span className="text-muted-foreground text-sm">
                        {emptyStateText}
                      </span>
                    ),
                  )
                : table.getRowModel().rows.map((row) => {
                    const externallySelected =
                      isRowSelected?.(row.original) ?? false
                    return (
                      <TableRow
                        key={row.id}
                        data-state={
                          externallySelected ? "selected" : undefined
                        }
                        className={cn(onRowClick && "cursor-pointer")}
                        onClick={
                          onRowClick
                            ? () => onRowClick(row.original)
                            : undefined
                        }
                      >
                        {row.getVisibleCells().map((cell) => {
                          const isDragged =
                            draggedColumnId === cell.column.id
                          // Dragged column uses the live pointer offset; other
                          // columns mirror their header's sortable transform
                          // (including when it animates back to 0) so the body
                          // stays in sync with the header's shift and return.
                          const columnTransform = columnTransforms[cell.column.id]
                          const shiftX = isDragged
                            ? dragOffsetX
                            : (columnTransform?.x ?? 0)
                          const cellStyle: React.CSSProperties = {
                            transform: `translate3d(${shiftX}px, 0, 0)`,
                            transition: isDragged
                              ? undefined
                              : columnTransform?.transition,
                            zIndex: isDragged ? 1 : undefined,
                            position: isDragged ? "relative" : undefined,
                          }
                          return (
                            <TableCell
                              key={cell.id}
                              style={cellStyle}
                              className={cn(
                                "truncate",
                                cell.column.columnDef.meta?.cellClassName,
                                isDragged && "bg-accent/60",
                              )}
                            >
                              {flexRender(
                                cell.column.columnDef.cell,
                                cell.getContext(),
                              )}
                            </TableCell>
                          )
                        })}
                      </TableRow>
                    )
                  })}
        </TableBody>
      </Table>
    </DndContext>
  )
}
