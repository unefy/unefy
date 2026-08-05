import Link from "next/link"
import { getTranslations } from "next-intl/server"

import { DateCell } from "@/components/ui/date-cell"
import { listMemberAttendance } from "@/lib/attendance"

/** Attendance tab: every recorded presence, most recent first. */
export default async function MemberAttendancePage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>
  searchParams: Promise<{ page?: string }>
}) {
  const [t, { id }, { page: rawPage }] = await Promise.all([
    getTranslations("members.detail.attendanceTab"),
    params,
    searchParams,
  ])
  const page = Math.max(1, Number(rawPage) || 1)

  const result = await listMemberAttendance(id, page).catch(() => null)
  const records = result?.data ?? []
  const totalPages = result?.meta.total_pages ?? 1

  return (
    <section className="space-y-3">
      <h2 className="text-sm font-medium text-muted-foreground">
        {t("title", { count: result?.meta.total ?? 0 })}
      </h2>

      {records.length === 0 ? (
        <div className="rounded-md border p-4 text-sm text-muted-foreground">
          {t("empty")}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-xs text-muted-foreground">
                <th className="p-3 text-start font-medium">{t("date")}</th>
                <th className="p-3 text-start font-medium">{t("session")}</th>
                <th className="p-3 text-start font-medium">{t("location")}</th>
              </tr>
            </thead>
            <tbody>
              {records.map((record) => (
                <tr key={record.id} className="border-b last:border-b-0">
                  <td className="p-3">
                    <DateCell value={record.occurred_on} dateOnly />
                  </td>
                  <td className="p-3">
                    <Link
                      href={`/attendance/${record.session_id}`}
                      className="hover:underline"
                    >
                      {record.session_title ?? "—"}
                    </Link>
                  </td>
                  <td className="p-3">{record.session_location ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center gap-2 text-sm">
          {page > 1 && (
            <Link
              href={`/members/${id}/attendance?page=${page - 1}`}
              className="text-muted-foreground hover:text-foreground"
            >
              ← {t("previous")}
            </Link>
          )}
          <span className="text-muted-foreground">
            {t("pageOf", { page, total: totalPages })}
          </span>
          {page < totalPages && (
            <Link
              href={`/members/${id}/attendance?page=${page + 1}`}
              className="text-muted-foreground hover:text-foreground"
            >
              {t("next")} →
            </Link>
          )}
        </div>
      )}
    </section>
  )
}
