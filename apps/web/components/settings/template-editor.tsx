"use client"

import { useRouter } from "next/navigation"
import { useEffect, useRef, useState, useTransition } from "react"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import {
  previewTemplateAction,
  saveTemplateAction,
  type TemplateInput,
} from "@/actions/documents"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import { completeAt, openPlaceholder } from "@/lib/template-completion"
import type {
  DocumentTemplate,
  DocumentVariable,
  StarterTemplate,
} from "@/lib/types/document"
import { AlertTriangleIcon, InfoIcon } from "lucide-react"

export function TemplateEditor({
  template,
  variables,
  starter = null,
}: {
  template: DocumentTemplate | null
  variables: DocumentVariable[]
  /** A ready-made wording to begin from. Its caveat stays on screen while the
   * club edits — that is the point of shipping one. */
  starter?: StarterTemplate | null
}) {
  const t = useTranslations("documents")
  const router = useRouter()
  const [pending, startTransition] = useTransition()
  const bodyRef = useRef<HTMLTextAreaElement>(null)

  const [form, setForm] = useState<TemplateInput>({
    name: template?.name ?? starter?.name ?? "",
    title: template?.title ?? starter?.title ?? "",
    body: template?.body ?? starter?.body ?? "",
    include_letterhead:
      template?.include_letterhead ?? starter?.include_letterhead ?? true,
    include_footer: template?.include_footer ?? starter?.include_footer ?? true,
    verifiable: template?.verifiable ?? starter?.verifiable ?? true,
    is_active: template?.is_active ?? true,
  })

  const [rendered, setRendered] = useState("")
  const [unknown, setUnknown] = useState<string[]>([])

  // What is being typed into an open `{{`, or null. Held in state rather than
  // derived on render because it depends on the caret, which React does not
  // re-render for.
  const [completing, setCompleting] = useState<string | null>(null)
  const [highlighted, setHighlighted] = useState(0)

  const matches =
    completing === null
      ? []
      : variables.filter((v) =>
          v.key.toLowerCase().includes(completing.toLowerCase())
        )

  useEffect(() => {
    // Debounced: the club writes a letter, not a query per keystroke.
    const handle = setTimeout(() => {
      startTransition(async () => {
        const result = await previewTemplateAction(form.body)
        if (result.success && result.data) {
          setRendered(result.data.rendered)
          setUnknown(result.data.unknown)
        }
      })
    }, 350)
    return () => clearTimeout(handle)
  }, [form.body])

  function syncCompletion(element: HTMLTextAreaElement) {
    const open = openPlaceholder(element.value, element.selectionStart)
    setCompleting(open)
    setHighlighted(0)
  }

  /** Replaces the open `{{…` with the finished placeholder. */
  function insert(key: string) {
    const element = bodyRef.current
    if (!element) return

    const completed = completeAt(element.value, element.selectionStart, key)
    if (!completed) return

    setForm((current) => ({ ...current, body: completed.text }))
    setCompleting(null)

    // After React has written the new value, put the caret back where the
    // helper says — otherwise the writer has to find their place again.
    requestAnimationFrame(() => {
      element.focus()
      element.setSelectionRange(completed.caret, completed.caret)
    })
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (completing === null || matches.length === 0) return

    if (event.key === "ArrowDown") {
      event.preventDefault()
      setHighlighted((i) => (i + 1) % matches.length)
    } else if (event.key === "ArrowUp") {
      event.preventDefault()
      setHighlighted((i) => (i - 1 + matches.length) % matches.length)
    } else if (event.key === "Enter" || event.key === "Tab") {
      event.preventDefault()
      insert(matches[highlighted].key)
    } else if (event.key === "Escape") {
      event.preventDefault()
      setCompleting(null)
    }
  }

  function save() {
    startTransition(async () => {
      const result = await saveTemplateAction(template?.id ?? null, form)
      if (!result.success) {
        toast.error(t(`errors.${result.error}`))
        return
      }
      toast.success(t("saved"))
      router.push("/settings/documents")
      router.refresh()
    })
  }

  return (
    <div className="space-y-6">
      {starter ? (
        <Alert>
          <InfoIcon />
          <AlertDescription>
            <span className="font-medium">{t("starterNotice")}</span>{" "}
            {starter.caveat}
          </AlertDescription>
        </Alert>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="template-name">{t("fields.name")}</Label>
          <Input
            id="template-name"
            value={form.name}
            maxLength={255}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
          <p className="text-xs text-muted-foreground">{t("hints.name")}</p>
        </div>
        <div className="space-y-2">
          <Label htmlFor="template-title">{t("fields.title")}</Label>
          <Input
            id="template-title"
            value={form.title}
            maxLength={255}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
          />
          <p className="text-xs text-muted-foreground">{t("hints.title")}</p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_18rem]">
        <div className="space-y-2">
          <Label htmlFor="template-body">{t("fields.body")}</Label>
          <div className="relative">
            <Textarea
              id="template-body"
              ref={bodyRef}
              value={form.body}
              rows={16}
              maxLength={20000}
              className="font-mono text-sm"
              onChange={(e) => {
                setForm({ ...form, body: e.target.value })
                syncCompletion(e.currentTarget)
              }}
              onKeyUp={(e) => syncCompletion(e.currentTarget)}
              onClick={(e) => syncCompletion(e.currentTarget)}
              onKeyDown={onKeyDown}
              onBlur={() => setCompleting(null)}
            />

            {/* Anchored under the field rather than at the caret: measuring a
                caret inside a textarea needs a mirrored copy of it, and a list
                that always appears in the same place is easier to learn than
                one that moves. */}
            {completing !== null && matches.length > 0 ? (
              <ul className="absolute inset-x-0 top-full z-20 mt-1 max-h-64 overflow-auto rounded-lg border bg-popover p-1 shadow-md">
                {matches.map((variable, index) => (
                  <li key={variable.key}>
                    <button
                      type="button"
                      // mousedown, not click: the textarea's blur would close
                      // the list before a click ever landed.
                      onMouseDown={(e) => {
                        e.preventDefault()
                        insert(variable.key)
                      }}
                      onMouseEnter={() => setHighlighted(index)}
                      className={`flex w-full flex-col items-start gap-0.5 rounded-md px-2 py-1.5 text-left text-sm ${
                        index === highlighted ? "bg-accent" : ""
                      }`}
                    >
                      <span className="font-mono text-xs">
                        {"{{"}
                        {variable.key}
                        {"}}"}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {t(`variables.${variable.key}`)}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
          <p className="text-xs text-muted-foreground">{t("hints.body")}</p>

          {unknown.length > 0 ? (
            <p className="flex items-start gap-2 text-sm text-destructive">
              <AlertTriangleIcon className="mt-0.5 size-4 shrink-0" />
              <span>
                {t("unknownPlaceholders")}{" "}
                <span className="font-mono">{unknown.join(", ")}</span>
              </span>
            </p>
          ) : null}
        </div>

        <div className="space-y-3">
          <h2 className="text-sm font-medium">{t("variablesTitle")}</h2>
          <p className="text-xs text-muted-foreground">{t("variablesHint")}</p>
          <ul className="space-y-1">
            {variables.map((variable) => (
              <li key={variable.key}>
                <button
                  type="button"
                  onClick={() => {
                    const element = bodyRef.current
                    if (!element) return
                    const caret = element.selectionStart
                    setForm((current) => ({
                      ...current,
                      body:
                        current.body.slice(0, caret) +
                        `{{${variable.key}}}` +
                        current.body.slice(caret),
                    }))
                  }}
                  className="w-full rounded-md px-2 py-1 text-left hover:bg-accent"
                >
                  <span className="block font-mono text-xs">
                    {variable.key}
                  </span>
                  <span className="block text-xs text-muted-foreground">
                    {t(`variables.${variable.key}`)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <section className="space-y-2 rounded-lg border bg-muted/40 p-4">
        <h2 className="text-sm font-medium">{t("previewTitle")}</h2>
        <p className="text-xs text-muted-foreground">{t("previewHint")}</p>
        <p className="text-sm whitespace-pre-wrap">
          {rendered || t("previewEmpty")}
        </p>
      </section>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {(
          [
            "include_letterhead",
            "include_footer",
            "verifiable",
            "is_active",
          ] as const
        ).map((key) => (
          <div key={key} className="space-y-1.5">
            <Label htmlFor={`template-${key}`}>{t(`fields.${key}`)}</Label>
            <div className="flex h-9 items-center gap-3">
              <Switch
                id={`template-${key}`}
                checked={form[key]}
                onCheckedChange={(checked) =>
                  setForm({ ...form, [key]: checked === true })
                }
              />
              <span className="text-sm text-muted-foreground">
                {form[key] ? t("yes") : t("no")}
              </span>
            </div>
            <p className="text-xs text-muted-foreground">{t(`hints.${key}`)}</p>
          </div>
        ))}
      </div>

      <div className="flex justify-end gap-2">
        <Button
          variant="outline"
          onClick={() => router.push("/settings/documents")}
          disabled={pending}
        >
          {t("cancel")}
        </Button>
        <Button onClick={save} disabled={pending || unknown.length > 0}>
          {pending ? t("saving") : t("save")}
        </Button>
      </div>
    </div>
  )
}
