"use server"

import { revalidatePath } from "next/cache"
import { z } from "zod"

import { apiCall, ApiError } from "@/lib/api"
import {
  parseCompetitionForm,
  parseEntryForm,
  parseSessionForm,
} from "@/lib/competition-schema"
import type {
  Competition,
  CompetitionEntry,
  CompetitionSession,
} from "@/lib/types/competition"

export type ActionResult<T = unknown> =
  | { success: true; data?: T }
  | { success: false; error: string }

function toError<T>(error: unknown): ActionResult<T> {
  if (error instanceof ApiError) {
    if (error.status === 409) return { success: false, error: "conflict" }
    if (error.status === 403) return { success: false, error: "forbidden" }
    if (error.status === 404) return { success: false, error: "notFound" }
    if (error.status === 422) return { success: false, error: "validation" }
    return { success: false, error: "unknown" }
  }
  return { success: false, error: "unreachable" }
}

const uuid = z.string().uuid()

function refresh(competitionId?: string, sessionId?: string) {
  revalidatePath("/competitions")
  if (competitionId) {
    revalidatePath(`/competitions/${competitionId}`)
    if (sessionId) {
      revalidatePath(`/competitions/${competitionId}/sessions/${sessionId}`)
    }
  }
}

// --- Competitions ---

export async function createCompetitionAction(
  _prev: ActionResult | undefined,
  formData: FormData
): Promise<ActionResult<Competition>> {
  const parsed = parseCompetitionForm(formData)
  if (!parsed.success) return { success: false, error: "validation" }

  try {
    const created = await apiCall<Competition>("/api/v1/competitions", {
      method: "POST",
      body: JSON.stringify(parsed.data),
    })
    refresh(created.id)
    return { success: true, data: created }
  } catch (error) {
    return toError(error)
  }
}

export async function updateCompetitionAction(
  competitionId: string,
  _prev: ActionResult | undefined,
  formData: FormData
): Promise<ActionResult<Competition>> {
  if (!uuid.safeParse(competitionId).success) {
    return { success: false, error: "validation" }
  }
  const parsed = parseCompetitionForm(formData)
  if (!parsed.success) return { success: false, error: "validation" }

  try {
    const updated = await apiCall<Competition>(
      `/api/v1/competitions/${competitionId}`,
      { method: "PATCH", body: JSON.stringify(parsed.data) }
    )
    refresh(competitionId)
    return { success: true, data: updated }
  } catch (error) {
    return toError(error)
  }
}

export async function deleteCompetitionAction(
  competitionId: string
): Promise<ActionResult> {
  if (!uuid.safeParse(competitionId).success) {
    return { success: false, error: "validation" }
  }
  try {
    await apiCall(`/api/v1/competitions/${competitionId}`, {
      method: "DELETE",
    })
  } catch (error) {
    return toError(error)
  }
  refresh()
  return { success: true }
}

// --- Rounds ---

/**
 * Creates a round, optionally putting it in the calendar too.
 *
 * The calendar side is the same link the event page reads: registration runs
 * through the event, results through the round.
 */
export async function createSessionAction(
  competitionId: string,
  createEvent: boolean,
  _prev: ActionResult | undefined,
  formData: FormData
): Promise<ActionResult<CompetitionSession>> {
  if (!uuid.safeParse(competitionId).success) {
    return { success: false, error: "validation" }
  }
  const parsed = parseSessionForm(formData)
  if (!parsed.success) return { success: false, error: "validation" }

  try {
    const created = await apiCall<CompetitionSession>(
      `/api/v1/competitions/${competitionId}/sessions`,
      {
        method: "POST",
        body: JSON.stringify({
          ...parsed.data,
          create_calendar_event: createEvent,
        }),
      }
    )
    refresh(competitionId)
    if (createEvent) revalidatePath("/events")
    return { success: true, data: created }
  } catch (error) {
    return toError(error)
  }
}

/** Deleting a round also removes the calendar event it created. */
export async function deleteSessionAction(
  competitionId: string,
  sessionId: string
): Promise<ActionResult> {
  if (
    !uuid.safeParse(competitionId).success ||
    !uuid.safeParse(sessionId).success
  ) {
    return { success: false, error: "validation" }
  }
  try {
    await apiCall(
      `/api/v1/competitions/${competitionId}/sessions/${sessionId}`,
      { method: "DELETE" }
    )
  } catch (error) {
    return toError(error)
  }
  refresh(competitionId)
  revalidatePath("/events")
  return { success: true }
}

// --- Results ---

export async function createEntryAction(
  competitionId: string,
  sessionId: string,
  scoreUnit: string,
  _prev: ActionResult | undefined,
  formData: FormData
): Promise<ActionResult<CompetitionEntry>> {
  if (
    !uuid.safeParse(competitionId).success ||
    !uuid.safeParse(sessionId).success
  ) {
    return { success: false, error: "validation" }
  }
  const parsed = parseEntryForm(formData)
  if (!parsed.success) return { success: false, error: "validation" }

  try {
    const created = await apiCall<CompetitionEntry>(
      `/api/v1/competitions/${competitionId}/sessions/${sessionId}/entries`,
      {
        method: "POST",
        body: JSON.stringify({
          ...parsed.data,
          score_unit: scoreUnit,
          source: "manual",
          // The moment it was scored, as far as this client knows.
          recorded_at: new Date().toISOString(),
        }),
      }
    )
    refresh(competitionId, sessionId)
    return { success: true, data: created }
  } catch (error) {
    return toError(error)
  }
}

export async function updateEntryAction(
  competitionId: string,
  sessionId: string,
  entryId: string,
  _prev: ActionResult | undefined,
  formData: FormData
): Promise<ActionResult<CompetitionEntry>> {
  if (!uuid.safeParse(entryId).success) {
    return { success: false, error: "validation" }
  }
  const parsed = parseEntryForm(formData)
  if (!parsed.success) return { success: false, error: "validation" }

  try {
    const updated = await apiCall<CompetitionEntry>(
      `/api/v1/competitions/${competitionId}/sessions/${sessionId}/entries/${entryId}`,
      {
        method: "PATCH",
        body: JSON.stringify({
          score_value: parsed.data.score_value,
          notes: parsed.data.notes,
        }),
      }
    )
    refresh(competitionId, sessionId)
    return { success: true, data: updated }
  } catch (error) {
    return toError(error)
  }
}

export async function deleteEntryAction(
  competitionId: string,
  sessionId: string,
  entryId: string
): Promise<ActionResult> {
  if (!uuid.safeParse(entryId).success) {
    return { success: false, error: "validation" }
  }
  try {
    await apiCall(
      `/api/v1/competitions/${competitionId}/sessions/${sessionId}/entries/${entryId}`,
      { method: "DELETE" }
    )
  } catch (error) {
    return toError(error)
  }
  refresh(competitionId, sessionId)
  return { success: true }
}
