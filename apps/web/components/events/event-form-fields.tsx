"use client"

import { useTranslations } from "next-intl"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Switch } from "@/components/ui/switch"
import { DatePicker } from "@/components/ui/date-picker"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useCompetitions, useCompetitionSessions } from "@/hooks/use-competitions"
import type { ClubEvent, EventType } from "@/lib/types/event"

const NONE = "__none__"

export const EVENT_TYPES: EventType[] = [
  "training",
  "meeting",
  "celebration",
  "competition",
  "other",
]

export interface EventFormState {
  title: string
  event_type: EventType
  date: string
  time: string
  end_time: string
  location: string
  description: string
  registration_required: boolean
  max_participants: string
  competition_id: string
  session_id: string
}

export const EMPTY_EVENT_FORM: EventFormState = {
  title: "",
  event_type: "other",
  date: "",
  time: "",
  end_time: "",
  location: "",
  description: "",
  registration_required: false,
  max_participants: "",
  competition_id: "",
  session_id: "",
}

export function eventToFormState(event: ClubEvent): EventFormState {
  return {
    title: event.title,
    event_type: event.event_type,
    date: event.starts_at.slice(0, 10),
    time: event.all_day ? "" : event.starts_at.slice(11, 16),
    end_time: event.ends_at ? event.ends_at.slice(11, 16) : "",
    location: event.location ?? "",
    description: event.description ?? "",
    registration_required: event.registration_required,
    max_participants: event.max_participants?.toString() ?? "",
    competition_id: event.competition_id ?? "",
    session_id: event.session_id ?? "",
  }
}

export function eventFormToPayload(form: EventFormState) {
  const time = form.time || "00:00"
  return {
    title: form.title.trim(),
    event_type: form.event_type,
    starts_at: `${form.date}T${time}:00`,
    ends_at: form.end_time ? `${form.date}T${form.end_time}:00` : null,
    all_day: !form.time,
    location: form.location.trim() || null,
    description: form.description.trim() || null,
    registration_required: form.registration_required,
    max_participants: form.max_participants
      ? Number(form.max_participants)
      : null,
    competition_id: form.competition_id || null,
    session_id: form.session_id || null,
  }
}

interface EventFormFieldsProps {
  form: EventFormState
  onChange: <K extends keyof EventFormState>(
    name: K,
    value: EventFormState[K],
  ) => void
}

export function EventFormFields({ form, onChange }: EventFormFieldsProps) {
  const t = useTranslations("events")

  const typeItems = EVENT_TYPES.map((type) => ({
    value: type,
    label: t(`type_${type}`),
  }))

  const { data: competitionsData } = useCompetitions()
  const { data: sessionsData } = useCompetitionSessions(form.competition_id)

  const competitionItems = [
    { value: NONE, label: t("noCompetition") },
    ...(competitionsData?.data ?? []).map((c) => ({
      value: c.id,
      label: c.name,
    })),
  ]
  const sessionItems = [
    { value: NONE, label: t("noSession") },
    ...(sessionsData?.data ?? []).map((s) => ({
      value: s.id,
      label: s.name ? `${s.name} (${s.date})` : s.date,
    })),
  ]

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>{t("eventTitle")} *</Label>
        <Input
          value={form.title}
          onChange={(e) => onChange("title", e.target.value)}
          placeholder={t("eventTitlePlaceholder")}
        />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>{t("type")}</Label>
          <Select
            items={typeItems}
            value={form.event_type}
            onValueChange={(v) => onChange("event_type", v as EventType)}
          >
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {typeItems.map((item) => (
                <SelectItem key={item.value} value={item.value}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label>{t("date")} *</Label>
          <DatePicker value={form.date} onChange={(v) => onChange("date", v)} />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>{t("startTime")}</Label>
          <Input
            type="time"
            value={form.time}
            onChange={(e) => onChange("time", e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label>{t("endTime")}</Label>
          <Input
            type="time"
            value={form.end_time}
            onChange={(e) => onChange("end_time", e.target.value)}
          />
        </div>
      </div>
      <div className="space-y-2">
        <Label>{t("location")}</Label>
        <Input
          value={form.location}
          onChange={(e) => onChange("location", e.target.value)}
          placeholder={t("locationPlaceholder")}
        />
      </div>
      <div className="space-y-2">
        <Label>{t("eventDescription")}</Label>
        <Textarea
          value={form.description}
          onChange={(e) => onChange("description", e.target.value)}
          placeholder={t("eventDescriptionPlaceholder")}
          className="min-h-16 text-sm"
        />
      </div>
      <div className="flex items-center justify-between">
        <Label>{t("registrationRequired")}</Label>
        <Switch
          checked={form.registration_required}
          onCheckedChange={(v) => onChange("registration_required", v)}
        />
      </div>
      <div className="space-y-2">
        <Label>{t("maxParticipants")}</Label>
        <Input
          inputMode="numeric"
          value={form.max_participants}
          onChange={(e) => onChange("max_participants", e.target.value)}
          placeholder={t("maxParticipantsPlaceholder")}
        />
      </div>
      <div className="space-y-2">
        <Label>{t("linkCompetition")}</Label>
        <Select
          items={competitionItems}
          value={form.competition_id || NONE}
          onValueChange={(v) => {
            onChange("competition_id", v === NONE || v === null ? "" : v)
            onChange("session_id", "")
          }}
        >
          <SelectTrigger className="w-full">
            <SelectValue placeholder={t("selectCompetition")} />
          </SelectTrigger>
          <SelectContent>
            {competitionItems.map((item) => (
              <SelectItem key={item.value} value={item.value}>
                {item.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      {form.competition_id && (
        <div className="space-y-2">
          <Label>{t("session")}</Label>
          <Select
            items={sessionItems}
            value={form.session_id || NONE}
            onValueChange={(v) =>
              onChange("session_id", v === NONE || v === null ? "" : v)
            }
          >
            <SelectTrigger className="w-full">
              <SelectValue placeholder={t("selectSession")} />
            </SelectTrigger>
            <SelectContent>
              {sessionItems.map((item) => (
                <SelectItem key={item.value} value={item.value}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}
    </div>
  )
}
