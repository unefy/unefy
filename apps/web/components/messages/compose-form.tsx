"use client"

import { useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import {
  previewAudienceAction,
  queueMessageAction,
  sendTestMessageAction,
} from "@/actions/messages"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { ConfirmAction } from "@/components/ui/confirm-action"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import type { ClubEvent } from "@/lib/types/event"
import type { ClubFunction } from "@/lib/types/functions"
import type {
  Audience,
  AudiencePreview,
  MessageKind,
} from "@/lib/types/message"
import { SendIcon, UsersIcon } from "lucide-react"

type AudienceType = Audience["type"]

/**
 * Writing a round mail, and knowing who gets it before it goes.
 *
 * The count comes from the backend's own resolution rather than from anything
 * counted here — it is the number that will actually go out, held-back rows
 * and all. Recomputed whenever the selection or the kind changes, because a
 * notice and a newsletter reach different people out of the same selection.
 */
export function ComposeForm({
  functions,
  events,
  currentYear,
  ownEmail,
}: {
  functions: ClubFunction[]
  events: ClubEvent[]
  currentYear: number
  /** Prefilled as the test recipient: whoever is composing is reading it. */
  ownEmail: string
}) {
  const t = useTranslations("messages")
  const router = useRouter()
  const [pending, startTransition] = useTransition()

  const [kind, setKind] = useState<MessageKind>("notice")
  const [subject, setSubject] = useState("")
  const [body, setBody] = useState("")

  const [audienceType, setAudienceType] = useState<AudienceType>("all")
  const [functionId, setFunctionId] = useState(functions[0]?.id ?? "")
  const [eventId, setEventId] = useState(events[0]?.id ?? "")
  const [includeWaitlist, setIncludeWaitlist] = useState(false)
  const [year, setYear] = useState(String(currentYear))

  const [preview, setPreview] = useState<AudiencePreview | null>(null)
  const [testTo, setTestTo] = useState(ownEmail)

  function audience(): Audience | null {
    switch (audienceType) {
      case "all":
        return { type: "all" }
      case "function":
        return functionId ? { type: "function", id: functionId } : null
      case "event":
        return eventId
          ? { type: "event", id: eventId, include_waitlist: includeWaitlist }
          : null
      case "debtors":
        return { type: "debtors", year: Number(year) }
    }
  }

  /** Any change to the selection makes the count stale, so it goes away. */
  function invalidate() {
    setPreview(null)
  }

  function check() {
    const selection = audience()
    if (!selection) return
    startTransition(async () => {
      const result = await previewAudienceAction({ kind, audience: selection })
      if (result.success) {
        if (result.data) setPreview(result.data)
      } else {
        toast.error(t(`errors.${result.error}`))
      }
    })
  }

  const ready =
    subject.trim() !== "" && body.trim() !== "" && audience() !== null

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="kind">{t("fields.kind")}</Label>
          <Select
            value={kind}
            onValueChange={(value) => {
              setKind(String(value) as MessageKind)
              // A notice and a newsletter reach different people out of the
              // same selection — the old count no longer applies.
              invalidate()
            }}
          >
            <SelectTrigger id="kind" className="w-full">
              <SelectValue>{() => t(`kinds.${kind}`)}</SelectValue>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="notice">{t("kinds.notice")}</SelectItem>
              <SelectItem value="newsletter">
                {t("kinds.newsletter")}
              </SelectItem>
            </SelectContent>
          </Select>
          <p className="text-sm text-muted-foreground">
            {t(`kindHints.${kind}`)}
          </p>
        </div>

        <div className="space-y-2">
          <Label htmlFor="audience">{t("fields.audience")}</Label>
          <Select
            value={audienceType}
            onValueChange={(value) => {
              setAudienceType(String(value) as AudienceType)
              invalidate()
            }}
          >
            <SelectTrigger id="audience" className="w-full">
              <SelectValue>{() => t(`audiences.${audienceType}`)}</SelectValue>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t("audiences.all")}</SelectItem>
              <SelectItem value="function">
                {t("audiences.function")}
              </SelectItem>
              <SelectItem value="event">{t("audiences.event")}</SelectItem>
              <SelectItem value="debtors">{t("audiences.debtors")}</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {audienceType === "function" && (
        <div className="space-y-2">
          <Label htmlFor="function">{t("fields.function")}</Label>
          {functions.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t("noFunctions")}</p>
          ) : (
            <Select
              value={functionId}
              onValueChange={(value) => {
                setFunctionId(String(value))
                invalidate()
              }}
            >
              <SelectTrigger id="function" className="w-full">
                <SelectValue>
                  {(value: string) =>
                    functions.find((f) => f.id === value)?.name ?? t("choose")
                  }
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {functions.map((entry) => (
                  <SelectItem key={entry.id} value={entry.id}>
                    {entry.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>
      )}

      {audienceType === "event" && (
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="event">{t("fields.event")}</Label>
            {events.length === 0 ? (
              <p className="text-sm text-muted-foreground">{t("noEvents")}</p>
            ) : (
              <Select
                value={eventId}
                onValueChange={(value) => {
                  setEventId(String(value))
                  invalidate()
                }}
              >
                <SelectTrigger id="event" className="w-full">
                  <SelectValue>
                    {(value: string) =>
                      events.find((e) => e.id === value)?.title ?? t("choose")
                    }
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {events.map((entry) => (
                    <SelectItem key={entry.id} value={entry.id}>
                      {entry.title}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>
          <div className="flex items-center gap-3">
            <Switch
              id="waitlist"
              checked={includeWaitlist}
              onCheckedChange={(checked) => {
                setIncludeWaitlist(checked === true)
                invalidate()
              }}
            />
            <Label htmlFor="waitlist">{t("fields.includeWaitlist")}</Label>
          </div>
        </div>
      )}

      {audienceType === "debtors" && (
        <div className="space-y-2">
          <Label htmlFor="year">{t("fields.year")}</Label>
          <Input
            id="year"
            inputMode="numeric"
            className="w-32"
            value={year}
            onChange={(event) => {
              setYear(event.target.value)
              invalidate()
            }}
          />
        </div>
      )}

      <div className="space-y-2">
        <Label htmlFor="subject">{t("fields.subject")}</Label>
        <Input
          id="subject"
          value={subject}
          onChange={(event) => setSubject(event.target.value)}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="body">{t("fields.body")}</Label>
        <Textarea
          id="body"
          rows={12}
          value={body}
          onChange={(event) => setBody(event.target.value)}
        />
        <p className="text-sm text-muted-foreground">{t("bodyHint")}</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <UsersIcon className="size-4" />
            {t("preview.title")}
          </CardTitle>
          <CardDescription>{t("preview.hint")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Button
            type="button"
            variant="outline"
            disabled={pending || audience() === null}
            onClick={check}
          >
            {t("preview.check")}
          </Button>

          {preview && <PreviewSummary preview={preview} />}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("test.title")}</CardTitle>
          <CardDescription>{t("test.hint")}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-end gap-3">
            <div className="space-y-2">
              <Label htmlFor="testTo">{t("test.to")}</Label>
              <Input
                id="testTo"
                type="email"
                className="w-72"
                value={testTo}
                onChange={(event) => setTestTo(event.target.value)}
              />
            </div>
            <Button
              type="button"
              variant="outline"
              disabled={pending || !ready || testTo.trim() === ""}
              onClick={() =>
                startTransition(async () => {
                  const result = await sendTestMessageAction({
                    subject,
                    body,
                    to: testTo,
                  })
                  if (!result.success) {
                    toast.error(t(`errors.${result.error}`))
                    return
                  }
                  // "delivered: false" is a real answer, not a failure: an
                  // installation that holds member mail back holds this back
                  // too, and "sent" would be a lie discovered by waiting.
                  if (result.data?.delivered) {
                    toast.success(t("test.sent"))
                  } else {
                    toast.warning(t("test.heldBack"))
                  }
                })
              }
            >
              {t("test.send")}
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="flex flex-wrap items-center gap-3">
        <ConfirmAction
          title={t("confirmSend.title")}
          description={
            preview
              ? t("confirmSend.description", { count: preview.summary.pending })
              : t("confirmSend.withoutPreview")
          }
          confirmLabel={t("send")}
          successMessage={t("queued")}
          variant="default"
          action={async () => {
            const selection = audience()
            if (!selection) return { success: false, error: "validation" }
            const result = await queueMessageAction({
              kind,
              subject,
              body,
              audience: selection,
            })
            if (result.success && result.data) {
              router.push(`/messages/${result.data.id}`)
            }
            // The raw key: ConfirmAction resolves it against its own
            // `common.confirm.errors`, so translating here would produce a
            // sentence looked up as a key.
            return result.success
              ? { success: true }
              : { success: false, error: result.error }
          }}
          trigger={
            <Button disabled={pending || !ready}>
              <SendIcon />
              {t("send")}
            </Button>
          }
        />
        {!preview && (
          // Not a blocker: the confirmation says the count is unknown, and a
          // board member who knows what they are doing should not be made to
          // click twice for it.
          <p className="text-sm text-muted-foreground">{t("preview.advice")}</p>
        )}
      </div>
    </div>
  )
}

/**
 * The counts, and every skipped kind said in words.
 *
 * `not_asked` sits apart from `refused` because they call for opposite
 * actions — ask them, or leave them alone — and a single "12 skipped" would
 * hide which of the two this is.
 */
function PreviewSummary({ preview }: { preview: AudiencePreview }) {
  const t = useTranslations("messages")
  const { summary } = preview

  const skipped: [string, number][] = [
    ["noEmail", summary.skipped_no_email],
    ["refused", summary.skipped_refused],
    ["notAsked", summary.skipped_not_asked],
    ["duplicate", summary.skipped_duplicate],
    ["heldBack", summary.skipped_held_back],
  ]

  return (
    <div className="space-y-3">
      <p className="text-2xl font-semibold tabular-nums">
        {t("preview.count", { count: summary.pending })}
      </p>

      <div className="flex flex-wrap gap-2">
        {skipped
          .filter(([, count]) => count > 0)
          .map(([reason, count]) => (
            <Badge
              key={reason}
              // Held back is the installation's own doing and the one a board
              // member can act on immediately, so it is the one that shouts.
              variant={reason === "heldBack" ? "destructive" : "outline"}
            >
              {t(`preview.skipped.${reason}`, { count })}
            </Badge>
          ))}
      </div>

      {summary.skipped_held_back > 0 && (
        <p className="text-sm text-destructive">{t("preview.heldBackHint")}</p>
      )}

      {preview.recipients.length > 0 && (
        <details className="text-sm">
          <summary className="cursor-pointer text-muted-foreground">
            {t("preview.names")}
          </summary>
          <ul className="mt-2 space-y-1">
            {preview.recipients.map((row) => (
              <li key={row.member_id} className="text-muted-foreground">
                {row.first_name} {row.last_name}
                {row.status === "skipped" && row.reason
                  ? ` — ${t(`preview.skippedShort.${row.reason}`)}`
                  : ""}
              </li>
            ))}
          </ul>
          {preview.truncated && (
            <p className="mt-2 text-muted-foreground">
              {t("preview.truncated")}
            </p>
          )}
        </details>
      )}
    </div>
  )
}
