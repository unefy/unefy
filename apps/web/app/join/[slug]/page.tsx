import type { Metadata } from "next"
import { getTranslations } from "next-intl/server"

import { JoinForm } from "@/components/members/join-form"
import { getJoinForm } from "@/lib/applications"

/**
 * The page somebody fills in to join a club.
 *
 * Public and unauthenticated: the reader has no account and is not supposed to
 * need one. A club that has not switched its form on renders as "not found" —
 * the same page as a club that does not exist, so this URL cannot be used to
 * find out which clubs are hosted here.
 */

export const dynamic = "force-dynamic"

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>
}): Promise<Metadata> {
  const [t, { slug }] = await Promise.all([getTranslations("join"), params])
  const form = await getJoinForm(slug)
  return {
    title: form ? t("metaTitle", { club: form.club_name }) : t("closed.title"),
  }
}

export default async function JoinPage({
  params,
}: {
  params: Promise<{ slug: string }>
}) {
  const [t, { slug }] = await Promise.all([getTranslations("join"), params])
  const form = await getJoinForm(slug)

  if (!form) {
    return (
      <main className="mx-auto flex min-h-svh max-w-lg flex-col justify-center gap-3 p-6 text-center">
        <h1 className="text-xl font-semibold">{t("closed.title")}</h1>
        <p className="text-sm text-muted-foreground">
          {t("closed.description")}
        </p>
      </main>
    )
  }

  return (
    <main className="mx-auto max-w-2xl space-y-8 p-6 py-12">
      <div className="space-y-2">
        <p className="text-sm text-muted-foreground">{form.club_name}</p>
        <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
        <p className="text-sm text-muted-foreground">
          {t("description", { club: form.club_name })}
        </p>
      </div>

      <JoinForm slug={slug} form={form} />
    </main>
  )
}
