export function MembersTableSkeleton() {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <div className="h-9 flex-1 max-w-sm animate-pulse rounded-3xl bg-muted" />
        <div className="h-9 w-32 animate-pulse rounded-3xl bg-muted" />
      </div>
      <div className="rounded-2xl border">
        <div className="border-b px-4 py-3">
          <div className="flex gap-8">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-4 w-20 animate-pulse rounded bg-muted" />
            ))}
          </div>
        </div>
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="border-b px-4 py-3 last:border-0">
            <div className="flex gap-8">
              {Array.from({ length: 5 }).map((_, j) => (
                <div key={j} className="h-4 w-24 animate-pulse rounded bg-muted" />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
