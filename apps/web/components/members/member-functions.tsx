"use client"

import { useMemo, useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import {
  assignMemberFunctionAction,
  deleteMemberFunctionAction,
  updateMemberFunctionAction,
} from "@/actions/functions"
import { ConfirmDelete } from "@/components/admin/confirm-delete"
import { Button } from "@/components/ui/button"
import { DateCell } from "@/components/ui/date-cell"
import {
  Dialog,
  DialogBody,
  DialogClose,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { roleLabel } from "@/lib/labels"
import type {
  ClubDivision,
  ClubFunction,
  MemberFunction,
} from "@/lib/types/functions"
import { FlagIcon, PlusIcon } from "lucide-react"

/** Auth-role ranking for the suggested-role hint. */
const ROLE_RANK: Record<string, number> = {
  member: 0,
  board: 1,
  admin: 2,
  owner: 3,
}

function today(): string {
  return new Date().toISOString().slice(0, 10)
}

function isCurrent(assignment: MemberFunction): boolean {
  return assignment.valid_to === null || assignment.valid_to >= today()
}

export function MemberFunctions({
  memberId,
  assignments,
  functions,
  divisions,
  hasDivisions,
  linkedRole,
}: {
  memberId: string
  assignments: MemberFunction[]
  functions: ClubFunction[]
  divisions: ClubDivision[]
  hasDivisions: boolean
  /** Auth role of the member's linked account, if any. */
  linkedRole: string | null
}) {
  const t = useTranslations("members.functionsTab")

  const current = assignments.filter(isCurrent)
  const history = assignments.filter((a) => !isCurrent(a))

  return (
    <>
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium text-muted-foreground">
            {t("current")}
          </h2>
          <AssignDialog
            memberId={memberId}
            functions={functions}
            divisions={divisions}
            hasDivisions={hasDivisions}
            linkedRole={linkedRole}
          />
        </div>
        <AssignmentsTable
          rows={current}
          memberId={memberId}
          hasDivisions={hasDivisions}
          emptyText={t("noCurrent")}
          withActions
        />
      </section>

      <section className="mt-8 space-y-3">
        <h2 className="text-sm font-medium text-muted-foreground">
          {t("history")}
        </h2>
        <AssignmentsTable
          rows={history}
          memberId={memberId}
          hasDivisions={hasDivisions}
          emptyText={t("noHistory")}
        />
      </section>
    </>
  )
}

function AssignmentsTable({
  rows,
  memberId,
  hasDivisions,
  emptyText,
  withActions = false,
}: {
  rows: MemberFunction[]
  memberId: string
  hasDivisions: boolean
  emptyText: string
  withActions?: boolean
}) {
  const t = useTranslations("members.functionsTab")

  if (rows.length === 0) {
    return <p className="text-sm text-muted-foreground">{emptyText}</p>
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{t("columns.function")}</TableHead>
            {hasDivisions && <TableHead>{t("columns.division")}</TableHead>}
            <TableHead>{t("columns.from")}</TableHead>
            <TableHead>{t("columns.to")}</TableHead>
            <TableHead>{t("columns.note")}</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.id}>
              <TableCell className="font-medium">{row.function_name}</TableCell>
              {hasDivisions && (
                <TableCell className="text-muted-foreground">
                  {row.division_name ?? "—"}
                </TableCell>
              )}
              <TableCell>
                <DateCell value={row.valid_from} dateOnly />
              </TableCell>
              <TableCell>
                {row.valid_to ? (
                  <DateCell value={row.valid_to} dateOnly />
                ) : (
                  <span className="text-muted-foreground">{t("ongoing")}</span>
                )}
              </TableCell>
              <TableCell className="text-muted-foreground">
                {row.note ?? "—"}
              </TableCell>
              <TableCell>
                <div className="flex justify-end">
                  {withActions && row.valid_to === null && (
                    <EndTermDialog memberId={memberId} assignment={row} />
                  )}
                  <DeleteAssignment memberId={memberId} assignment={row} />
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function AssignDialog({
  memberId,
  functions,
  divisions,
  hasDivisions,
  linkedRole,
}: {
  memberId: string
  functions: ClubFunction[]
  divisions: ClubDivision[]
  hasDivisions: boolean
  linkedRole: string | null
}) {
  const t = useTranslations("members.functionsTab.assign")
  const tr = useTranslations("admin")
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pending, startTransition] = useTransition()

  const [functionId, setFunctionId] = useState("")
  const [divisionId, setDivisionId] = useState("")
  const [validFrom, setValidFrom] = useState(today())
  const [validTo, setValidTo] = useState("")
  const [note, setNote] = useState("")

  // Clubs without divisions never see division-level functions (the settings
  // dialog hides the level), but stale data must not brick the picker.
  const assignable = useMemo(
    () => functions.filter((f) => hasDivisions || f.level === "club"),
    [functions, hasDivisions]
  )
  const selected = assignable.find((f) => f.id === functionId)
  const needsDivision = selected?.level === "division"

  // The plan's key UX detail: suggest — never couple — the auth role.
  const roleHint =
    selected?.suggested_role &&
    linkedRole !== null &&
    (ROLE_RANK[selected.suggested_role] ?? 0) > (ROLE_RANK[linkedRole] ?? 0)
      ? t("roleHint", {
          role: roleLabel(tr, selected.suggested_role),
          current: roleLabel(tr, linkedRole),
        })
      : null

  function submit() {
    startTransition(async () => {
      const result = await assignMemberFunctionAction(memberId, {
        function_id: functionId,
        division_id: needsDivision && divisionId ? divisionId : null,
        valid_from: validFrom,
        valid_to: validTo || null,
        note,
      })

      if (result.success) {
        setOpen(false)
        setError(null)
        setFunctionId("")
        setDivisionId("")
        setValidTo("")
        setNote("")
        toast.success(t("created"))
        router.refresh()
      } else {
        setError(result.error === "conflict" ? t("overlap") : t("failed"))
      }
    })
  }

  const valid =
    functionId !== "" && validFrom !== "" && (!needsDivision || divisionId !== "")

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button size="sm">
            <PlusIcon />
            {t("open")}
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("title")}</DialogTitle>
        </DialogHeader>

        <DialogBody>
          <div className="space-y-2">
            <Label htmlFor="assign-function">{t("function")}</Label>
            <Select
              value={functionId}
              onValueChange={(value) => setFunctionId(String(value))}
            >
              <SelectTrigger id="assign-function" className="w-full">
                <SelectValue>
                  {(value: string) =>
                    assignable.find((f) => f.id === value)?.name ?? ""
                  }
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {assignable.map((f) => (
                    <SelectItem key={f.id} value={f.id}>
                      {f.name}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
            {roleHint && (
              <p className="text-xs text-muted-foreground">{roleHint}</p>
            )}
          </div>

          {needsDivision && (
            <div className="space-y-2">
              <Label htmlFor="assign-division">{t("division")}</Label>
              <Select
                value={divisionId}
                onValueChange={(value) => setDivisionId(String(value))}
              >
                <SelectTrigger id="assign-division" className="w-full">
                  <SelectValue>
                    {(value: string) =>
                      divisions.find((d) => d.id === value)?.name ?? ""
                    }
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {divisions.map((d) => (
                      <SelectItem key={d.id} value={d.id}>
                        {d.name}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="assign-from">{t("from")}</Label>
              <Input
                id="assign-from"
                type="date"
                value={validFrom}
                onChange={(e) => setValidFrom(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="assign-to">{t("to")}</Label>
              <Input
                id="assign-to"
                type="date"
                value={validTo}
                onChange={(e) => setValidTo(e.target.value)}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="assign-note">{t("note")}</Label>
            <Input
              id="assign-note"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder={t("notePlaceholder")}
            />
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}
        </DialogBody>

        <DialogFooter>
          <DialogClose
            render={
              <Button type="button" variant="outline">
                {t("cancel")}
              </Button>
            }
          />
          <Button onClick={submit} disabled={pending || !valid}>
            {pending ? t("saving") : t("save")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/** Ending a term sets `valid_to` — the row stays as history, never deleted. */
function EndTermDialog({
  memberId,
  assignment,
}: {
  memberId: string
  assignment: MemberFunction
}) {
  const t = useTranslations("members.functionsTab.end")
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pending, startTransition] = useTransition()
  const [validTo, setValidTo] = useState(today())

  function submit() {
    startTransition(async () => {
      const result = await updateMemberFunctionAction(memberId, assignment.id, {
        valid_to: validTo,
      })
      if (result.success) {
        setOpen(false)
        setError(null)
        toast.success(t("ended"))
        router.refresh()
      } else {
        setError(t("failed"))
      }
    })
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button variant="ghost" size="sm" aria-label={t("open")}>
            <FlagIcon />
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {t("title", { name: assignment.function_name })}
          </DialogTitle>
        </DialogHeader>

        <DialogBody>
          <div className="space-y-2">
            <Label htmlFor="end-date">{t("date")}</Label>
            <Input
              id="end-date"
              type="date"
              value={validTo}
              min={assignment.valid_from}
              onChange={(e) => setValidTo(e.target.value)}
            />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </DialogBody>

        <DialogFooter>
          <DialogClose
            render={
              <Button type="button" variant="outline">
                {t("cancel")}
              </Button>
            }
          />
          <Button onClick={submit} disabled={pending || !validTo}>
            {pending ? t("saving") : t("save")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function DeleteAssignment({
  memberId,
  assignment,
}: {
  memberId: string
  assignment: MemberFunction
}) {
  const t = useTranslations("members.functionsTab")

  return (
    <ConfirmDelete
      title={t("deleteTitle", { name: assignment.function_name })}
      description={t("deleteDescription")}
      action={async () => deleteMemberFunctionAction(memberId, assignment.id)}
    />
  )
}
