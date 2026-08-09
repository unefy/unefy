"use client"

import { useTransition } from "react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import { registerSelfAction, unregisterSelfAction } from "@/actions/events"
import { Button } from "@/components/ui/button"
import { CalendarCheckIcon, CalendarXIcon } from "lucide-react"

/**
 * The member's own register/cancel button.
 *
 * Deliberately does not decide whether a seat is free — the backend waitlists
 * when the event is full, and guessing here would only produce a second,
 * disagreeing answer.
 */
export function SelfRegistration({
  eventId,
  isRegistered,
  disabled = false,
}: {
  eventId: string
  isRegistered: boolean
  /** Cancelled or past events: nothing to sign up to. */
  disabled?: boolean
}) {
  const t = useTranslations("events.registration")
  const router = useRouter()
  const [pending, startTransition] = useTransition()

  function submit() {
    startTransition(async () => {
      const result = isRegistered
        ? await unregisterSelfAction(eventId)
        : await registerSelfAction(eventId)

      if (result.success) {
        toast.success(isRegistered ? t("cancelledToast") : t("registeredToast"))
        router.refresh()
      } else {
        toast.error(t(`errors.${result.error}`))
      }
    })
  }

  return (
    <Button
      variant={isRegistered ? "outline" : "default"}
      size="sm"
      disabled={pending || disabled}
      onClick={submit}
    >
      {isRegistered ? <CalendarXIcon /> : <CalendarCheckIcon />}
      {isRegistered ? t("cancel") : t("register")}
    </Button>
  )
}
