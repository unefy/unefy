/**
 * The autocomplete's one piece of logic, kept out of the component so it can
 * be tested: everything else in the editor is wiring.
 */

/**
 * An open `{{` up to the caret, and what has been typed into it.
 *
 * Only counts when there is no closing brace and no newline in between: once
 * the placeholder is finished, or the writer has moved on to the next line,
 * there is nothing left to complete.
 *
 * Returns "" for a bare `{{` — that is an open placeholder with nothing typed
 * yet, and the list should appear. Null means no completion is running, which
 * is a different thing from an empty prefix.
 */
export function openPlaceholder(text: string, caret: number): string | null {
  const before = text.slice(0, caret)
  const start = before.lastIndexOf("{{")
  if (start === -1) return null

  const inner = before.slice(start + 2)
  if (inner.includes("}") || inner.includes("\n")) return null
  return inner
}

/** Replaces the open `{{…` before the caret with a finished placeholder. */
export function completeAt(
  text: string,
  caret: number,
  key: string
): { text: string; caret: number } | null {
  const start = text.slice(0, caret).lastIndexOf("{{")
  if (start === -1) return null

  return {
    text: text.slice(0, start) + `{{${key}}}` + text.slice(caret),
    // Behind what was inserted, so the writer keeps their place.
    caret: start + key.length + 4,
  }
}
