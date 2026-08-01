import { getTranslations } from "next-intl/server"

import { deleteDisciplineAction } from "@/actions/admin-catalog"
import { ConfirmDelete } from "@/components/admin/confirm-delete"
import { DisciplineDialog } from "@/components/admin/discipline-dialog"
import { DisciplinesTable } from "@/components/admin/disciplines-table"
import { PageHeader } from "@/components/admin/page-header"
import {
  ADMIN_PAGE_SIZE,
  listCatalogDisciplines,
  listSports,
} from "@/lib/admin"

export default async function AdminDisciplinesPage() {
  const t = await getTranslations("admin.disciplines")

  const [sports, { data, meta }] = await Promise.all([
    listSports(),
    listCatalogDisciplines({ perPage: ADMIN_PAGE_SIZE }),
  ])

  // Built here rather than in the table: each entry closes over a server
  // action, which only a Server Component can create.
  const actions = Object.fromEntries(
    data.map((discipline) => [
      discipline.id,
      <>
        <DisciplineDialog sports={sports} discipline={discipline} />
        <ConfirmDelete
          title={t("deleteTitle", { name: discipline.name })}
          description={t("deleteDescription")}
          action={async () => {
            "use server"
            return deleteDisciplineAction(discipline.id)
          }}
        />
      </>,
    ])
  )

  return (
    <>
      <PageHeader
        title={t("title")}
        description={t("description", { count: meta.total })}
      >
        <DisciplineDialog sports={sports} />
      </PageHeader>
      <DisciplinesTable disciplines={data} sports={sports} actions={actions} />
    </>
  )
}
