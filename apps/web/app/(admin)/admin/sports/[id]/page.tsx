import { notFound } from "next/navigation"
import { getTranslations } from "next-intl/server"

import { deleteUnitAction } from "@/actions/admin-catalog"
import { ConfirmDelete } from "@/components/admin/confirm-delete"
import { PageHeader } from "@/components/admin/page-header"
import { SportUnitsTable } from "@/components/admin/sport-units-table"
import { UnitDialog } from "@/components/admin/unit-dialog"
import { Badge } from "@/components/ui/badge"
import { listCatalogUnits, listSports } from "@/lib/admin"

export default async function AdminSportDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const [t, { id }] = await Promise.all([
    getTranslations("admin.sportDetail"),
    params,
  ])

  const [sports, units] = await Promise.all([
    listSports(),
    listCatalogUnits(id),
  ])
  const sport = sports.find((candidate) => candidate.id === id)
  if (!sport) notFound()

  // Built here rather than in the table: each entry closes over a server
  // action, which only a Server Component can create.
  const actions = Object.fromEntries(
    units.map((unit) => [
      unit.id,
      <>
        <UnitDialog sportId={sport.id} unit={unit} />
        <ConfirmDelete
          title={t("deleteUnitTitle", { name: unit.name })}
          description={t("deleteUnitDescription")}
          action={async () => {
            "use server"
            return deleteUnitAction(unit.id)
          }}
        />
      </>,
    ])
  )

  return (
    <>
      <PageHeader
        title={sport.name}
        description={sport.description ?? t("noDescription")}
      >
        <UnitDialog sportId={sport.id} />
      </PageHeader>

      <div className="flex flex-wrap gap-2">
        <Badge variant="outline" className="font-mono text-xs">
          {sport.key}
        </Badge>
        {sport.modules.map((module) => (
          <Badge key={module} variant="secondary">
            {module}
          </Badge>
        ))}
        <Badge variant={sport.is_active ? "secondary" : "outline"}>
          {sport.is_active ? t("active") : t("inactive")}
        </Badge>
      </div>

      <section className="space-y-3">
        <div className="space-y-1">
          <h2 className="text-sm font-medium text-muted-foreground">
            {t("units")}
          </h2>
          <p className="text-sm text-muted-foreground">{t("unitsHint")}</p>
        </div>
        <SportUnitsTable units={units} actions={actions} />
      </section>
    </>
  )
}
