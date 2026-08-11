import type { Metadata } from "next"
import { getTranslations } from "next-intl/server"

import { signingPageQuery } from "@/actions/documents"
import { SignForm } from "@/components/documents/sign-form"

/**
 * The page the QR on the club's screen leads to.
 *
 * Public and unauthenticated on purpose: whoever signs is standing there with
 * their own phone and has no session on it. The link itself is the
 * authorisation — 32 random bytes, a quarter of an hour, one named document,
 * spent on signing.
 *
 * It shows the document's full text, deliberately: nobody should be asked to
 * sign something they are not allowed to read.
 */

export const dynamic = "force-dynamic"

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("sign")
  return {
    title: t("title"),
    // A signing link is a credential. A crawler that followed one would put
    // the document in an index.
    robots: { index: false, follow: false },
  }
}

export default async function SignPage({
  params,
}: {
  params: Promise<{ token: string }>
}) {
  const { token } = await params
  const t = await getTranslations("sign")
  const document = await signingPageQuery(token)

  if (!document) {
    return (
      <main className="mx-auto flex min-h-svh max-w-md flex-col justify-center gap-2 p-6">
        <h1 className="text-xl font-semibold">{t("expiredTitle")}</h1>
        <p className="text-sm text-muted-foreground">{t("expiredHint")}</p>
      </main>
    )
  }

  return (
    <main className="mx-auto min-h-svh max-w-md space-y-6 p-6">
      <header className="space-y-1">
        <p className="text-xs tracking-wide text-muted-foreground uppercase">
          {document.club_name}
        </p>
        <h1 className="text-xl font-semibold">{document.title}</h1>
        <p className="text-sm text-muted-foreground">{document.member_name}</p>
      </header>

      <section className="max-h-64 overflow-y-auto rounded-lg border bg-muted/40 p-4">
        <p className="text-sm whitespace-pre-wrap">{document.body}</p>
      </section>

      <SignForm token={token} />
    </main>
  )
}
