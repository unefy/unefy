"use client"

import { useTransition } from "react"
import { useRouter } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"
import { toast } from "sonner"

import {
  checkInAction,
  checkOutAction,
  removeRecordAction,
} from "@/actions/attendance"
import { CorrectionDialog } from "@/components/attendance/correction-dialog"
import { MemberSearch } from "@/components/attendance/member-search"
import { ReasonDialog } from "@/components/attendance/reason-dialog"
import { RecordDetailDialog } from "@/components/shooting/record-detail-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatTime } from "@/lib/time"
import type {
  AttendanceRecord,
  AttendanceSessionDetail,
} from "@/lib/types/attendance"
import type { ClubDiscipline, ShootingRecordDetail } from "@/lib/types/shooting"
import { LogOutIcon, Trash2Icon } from "lucide-react"

export function AttendanceList({
  session,
  timeZone,
  shooting,
}: {
  session: AttendanceSessionDetail
  /** The club's zone — see `lib/time`. */
  timeZone: string
  /**
   * Present only for a club whose sports carry the shooting module. Undefined
   * means the column and its dialog do not exist here — not that they are empty.
   */
  shooting?: {
    details: ShootingRecordDetail[]
    disciplines: ClubDiscipline[]
  }
}) {
  const t = useTranslations("attendance")
  const tf = useTranslations("attendance.form")
  const locale = useLocale()
  const router = useRouter()
  const [pending, startTransition] = useTransition()

  const closed = session.status === "closed"
  const records = session.records

  const detailByRecord = new Map(
    (shooting?.details ?? []).map((detail) => [
      detail.attendance_record_id,
      detail,
    ])
  )

  const time = (value: string | null) =>
    value ? formatTime(value, locale, timeZone) : "—"

  function checkIn(memberId: string) {
    startTransition(async () => {
      const result = await checkInAction(session.id, memberId)
      if (result.success) {
        toast.success(t("toasts.checkedIn"))
        router.refresh()
      } else {
        toast.error(tf(`errors.${result.error}`))
      }
    })
  }

  function checkOut(record: AttendanceRecord) {
    startTransition(async () => {
      const result = await checkOutAction(session.id, record.id)
      if (result.success) {
        toast.success(t("toasts.checkedOut"))
        router.refresh()
      } else {
        toast.error(tf(`errors.${result.error}`))
      }
    })
  }

  return (
    <div className="space-y-4">
      {!closed && (
        <MemberSearch
          placeholder={t("search.placeholder")}
          actionLabel={t("checkIn")}
          takenIds={records.map((record) => record.member_id)}
          takenLabel={t("alreadyPresent")}
          disabled={pending}
          onSelect={(member) => checkIn(member.id)}
        />
      )}

      {records.length === 0 ? (
        <p className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
          {t("noRecords")}
        </p>
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("columns.member")}</TableHead>
                <TableHead className="w-24">{t("columns.number")}</TableHead>
                <TableHead className="w-24">{t("columns.checkedIn")}</TableHead>
                <TableHead className="w-24">
                  {t("columns.checkedOut")}
                </TableHead>
                <TableHead className="w-28">{t("columns.assurance")}</TableHead>
                {shooting && <TableHead>{t("shooting.column")}</TableHead>}
                <TableHead>{t("columns.note")}</TableHead>
                <TableHead className="w-px text-end">
                  {t("columns.actions")}
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {records.map((record) => (
                <TableRow key={record.id}>
                  <TableCell className="font-medium">
                    {record.member_name ?? "—"}
                  </TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground">
                    {record.member_number ?? "—"}
                  </TableCell>
                  <TableCell className="tabular-nums">
                    {time(record.checked_in_at)}
                  </TableCell>
                  <TableCell className="text-muted-foreground tabular-nums">
                    {time(record.checked_out_at)}
                  </TableCell>
                  <TableCell>
                    {/* The method is what was actually done; the assurance
                        level follows from it. Both are shown, because "ticked
                        off by the supervisor" is the honest description. */}
                    <Badge variant="outline" className="font-normal">
                      {t(`methods.${record.method}`)}
                    </Badge>
                  </TableCell>
                  {shooting && (
                    <TableCell className="text-sm text-muted-foreground">
                      <ShootingSummary
                        detail={detailByRecord.get(record.id)}
                        disciplines={shooting.disciplines}
                      />
                    </TableCell>
                  )}
                  <TableCell className="text-sm text-muted-foreground">
                    {record.note ?? "—"}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center justify-end gap-1">
                      {/* Checking out is a fresh claim about when somebody
                          left, not a correction, so it ends with the session.
                          Afterwards the same field can only be set through the
                          correction dialog, which insists on a reason. */}
                      {!closed && record.checked_out_at === null && (
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={pending}
                          onClick={() => checkOut(record)}
                          aria-label={t("checkOut")}
                          title={t("checkOut")}
                        >
                          <LogOutIcon />
                        </Button>
                      )}
                      {/* Guests excluded: the server refuses a detail on a
                          guest row (GUEST_RECORD), because a guest counts
                          towards no §14 proof. Offering the button would be a
                          promise the API breaks. */}
                      {shooting && record.member_id !== null && (
                        <RecordDetailDialog
                          sessionId={session.id}
                          recordId={record.id}
                          memberName={record.member_name ?? ""}
                          detail={detailByRecord.get(record.id)}
                          disciplines={shooting.disciplines}
                        />
                      )}
                      <CorrectionDialog
                        sessionId={session.id}
                        record={record}
                      />
                      <ReasonDialog
                        trigger={
                          <Button
                            variant="ghost"
                            size="sm"
                            aria-label={t("remove")}
                            title={t("remove")}
                          >
                            <Trash2Icon className="text-destructive" />
                          </Button>
                        }
                        title={t("removeDialog.title", {
                          name: record.member_name ?? "",
                        })}
                        description={t(
                          closed
                            ? "removeDialog.descriptionClosed"
                            : "removeDialog.description"
                        )}
                        confirmLabel={t("remove")}
                        successMessage={t("toasts.removed")}
                        action={(reason) =>
                          removeRecordAction(session.id, record.id, reason)
                        }
                      />
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}

/**
 * The three shooting fields in one cell.
 *
 * Compact because the row already carries six columns, and because most evenings
 * fill in one or two of the three — a table with three sparse columns reads worse
 * than one dense cell. An entry nobody made shows a dash, so a missing detail is
 * visibly missing rather than indistinguishable from a zero.
 */
function ShootingSummary({
  detail,
  disciplines,
}: {
  detail: ShootingRecordDetail | undefined
  disciplines: ClubDiscipline[]
}) {
  const t = useTranslations("attendance.shooting")

  if (!detail) return <>—</>

  const discipline = disciplines.find((d) => d.id === detail.club_discipline_id)
  const parts = [
    discipline?.short_name ?? discipline?.name,
    detail.weapon_category ? t(`weapons.${detail.weapon_category}`) : undefined,
    detail.rounds_fired === null
      ? undefined
      : t("roundsShort", { count: detail.rounds_fired }),
  ].filter(Boolean)

  return <>{parts.length > 0 ? parts.join(" · ") : "—"}</>
}
