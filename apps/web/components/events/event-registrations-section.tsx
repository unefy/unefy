"use client"

import { useState } from "react"
import Link from "next/link"
import { useTranslations } from "next-intl"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { SectionHeading } from "@/components/layout/section-heading"
import { useRegisterMember, useUnregisterMember } from "@/hooks/use-events"
import { useMembers } from "@/hooks/use-members"
import { useErrorMessage } from "@/lib/errors"
import { HugeiconsIcon } from "@hugeicons/react"
import { Delete02Icon } from "@hugeicons/core-free-icons"
import type { ClubEventDetail } from "@/lib/types/event"

interface EventRegistrationsSectionProps {
  event: ClubEventDetail
}

export function EventRegistrationsSection({
  event,
}: EventRegistrationsSectionProps) {
  const t = useTranslations("events")
  const tc = useTranslations("common")
  const getErrorMessage = useErrorMessage()

  const { data: membersData } = useMembers({ per_page: 100, status: "active" })
  const registerMember = useRegisterMember()
  const unregisterMember = useUnregisterMember()
  const [memberId, setMemberId] = useState("")

  const registeredMemberIds = new Set(
    event.registrations.map((r) => r.member_id),
  )
  const memberItems = (membersData?.data ?? [])
    .filter((m) => !registeredMemberIds.has(m.id))
    .map((m) => ({
      value: m.id,
      label: `${m.first_name} ${m.last_name}`,
    }))

  function handleRegister() {
    if (!memberId) return
    registerMember.mutate(
      { eventId: event.id, memberId },
      {
        onSuccess: (registration) => {
          toast.success(
            registration.status === "waitlist"
              ? t("addedToWaitlist")
              : tc("saved"),
          )
          setMemberId("")
        },
        onError: (err) => toast.error(getErrorMessage(err)),
      },
    )
  }

  return (
    <div>
      <SectionHeading
        title={`${t("registrations")} (${event.registered_count}${
          event.max_participants ? ` / ${event.max_participants}` : ""
        })`}
        description=""
      />
      {event.registrations.length === 0 ? (
        <p className="text-muted-foreground text-sm">{t("noRegistrations")}</p>
      ) : (
        <div className="space-y-2">
          {event.registrations.map((registration) => (
            <div
              key={registration.id}
              className="flex items-center justify-between rounded-lg border px-3 py-2"
            >
              <div className="flex min-w-0 items-center gap-2">
                <Link
                  href={`/members/${registration.member_id}`}
                  className="truncate text-sm font-medium hover:underline"
                >
                  {registration.member_name}
                </Link>
                {registration.status === "waitlist" && (
                  <Badge variant="outline">{t("waitlist")}</Badge>
                )}
              </div>
              <button
                onClick={() =>
                  unregisterMember.mutate(
                    { eventId: event.id, registrationId: registration.id },
                    {
                      onSuccess: () => toast.success(tc("saved")),
                      onError: (err) => toast.error(getErrorMessage(err)),
                    },
                  )
                }
                disabled={unregisterMember.isPending}
                className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
                aria-label={tc("delete")}
              >
                <HugeiconsIcon icon={Delete02Icon} size={15} />
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="mt-4 space-y-2">
        <Label>{t("registerMember")}</Label>
        <div className="flex gap-2">
          <Select
            items={memberItems}
            value={memberId || null}
            onValueChange={(v) => setMemberId(v ?? "")}
          >
            <SelectTrigger className="w-full">
              <SelectValue placeholder={t("selectMember")} />
            </SelectTrigger>
            <SelectContent>
              {memberItems.map((item) => (
                <SelectItem key={item.value} value={item.value}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            size="sm"
            onClick={handleRegister}
            disabled={!memberId || registerMember.isPending}
          >
            {registerMember.isPending ? tc("saving") : tc("create")}
          </Button>
        </div>
      </div>
    </div>
  )
}
