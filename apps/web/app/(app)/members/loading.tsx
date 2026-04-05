import { MembersTableSkeleton } from "@/components/skeletons/members-skeleton"

export default function Loading() {
  return (
    <div className="space-y-6">
      <div>
        <div className="h-8 w-32 animate-pulse rounded bg-muted" />
        <div className="mt-1 h-4 w-56 animate-pulse rounded bg-muted" />
      </div>
      <MembersTableSkeleton />
    </div>
  )
}
