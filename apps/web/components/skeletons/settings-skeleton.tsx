export function SettingsSkeleton() {
  return (
    <div className="space-y-8">
      <div className="flex items-start justify-between">
        <div>
          <div className="h-8 w-32 animate-pulse rounded bg-muted" />
          <div className="mt-1 h-4 w-56 animate-pulse rounded bg-muted" />
        </div>
        <div className="h-9 w-28 animate-pulse rounded-3xl bg-muted" />
      </div>
      <div className="flex gap-10">
        <div className="w-48 shrink-0 space-y-2">
          {Array.from({ length: 2 }).map((_, i) => (
            <div key={i} className="h-9 animate-pulse rounded-lg bg-muted" />
          ))}
        </div>
        <div className="flex-1 max-w-2xl space-y-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-10 animate-pulse rounded-3xl bg-muted" />
          ))}
        </div>
      </div>
    </div>
  )
}
