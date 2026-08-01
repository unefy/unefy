import { getTranslations } from "next-intl/server"

import { deleteSportAction } from "@/actions/admin-catalog"
import { ConfirmDelete } from "@/components/admin/confirm-delete"
import { PageHeader } from "@/components/admin/page-header"
import { SportDialog } from "@/components/admin/sport-dialog"
import { SportsTable } from "@/components/admin/sports-table"
import { listSportModules, listSports } from "@/lib/admin"

export default async function AdminSportsPage() {
  const [t, sports, modules] = await Promise.all([
    getTranslations("admin.sports"),
    listSports(),
    listSportModules(),
  ])

  // Built here rather than in the table: each entry closes over a server
  // action, which only a Server Component can create.
  const actions = Object.fromEntries(
    sports.map((sport) => [
      sport.id,
      <>
        <SportDialog sport={sport} modules={modules} />
        <ConfirmDelete
          title={t("deleteTitle", { name: sport.name })}
          description={t("deleteDescription")}
          action={async () => {
            "use server"
            return deleteSportAction(sport.id)
          }}
        />
      </>,
    ])
  )

  return (
    <>
      <PageHeader title={t("title")} description={t("description")}>
        <SportDialog modules={modules} />
      </PageHeader>
      <SportsTable sports={sports} actions={actions} />
    </>
  )
}
