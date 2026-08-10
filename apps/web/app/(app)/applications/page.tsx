import { getTranslations } from "next-intl/server"

import { ApplicationsTable } from "@/components/members/applications-table"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { listApplications } from "@/lib/applications"
import { getClub } from "@/lib/club"
import { InfoIcon } from "lucide-react"

/** What the public join form produced, and what the board has decided on. */
export default async function ApplicationsPage() {
  const [t, applications, club] = await Promise.all([
    getTranslations("applications"),
    listApplications().catch(() => []),
    getClub().catch(() => null),
  ])

  const joinUrl = club ? `/join/${club.slug}` : null

  return (
    <>
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          {t("description")}
        </p>
      </div>

      {club && !club.applications_enabled ? (
        <Alert>
          <InfoIcon />
          <AlertDescription>
            {t("closed.description")}{" "}
            <a className="underline underline-offset-4" href="/settings">
              {t("closed.action")}
            </a>
          </AlertDescription>
        </Alert>
      ) : joinUrl ? (
        <Alert>
          <InfoIcon />
          <AlertDescription>
            {t("open.description")}{" "}
            <a className="underline underline-offset-4" href={joinUrl}>
              {joinUrl}
            </a>
          </AlertDescription>
        </Alert>
      ) : null}

      <ApplicationsTable applications={applications} />
    </>
  )
}
