"use server"

import { revalidatePath } from "next/cache"
import { cookies } from "next/headers"

import type { ActionResult } from "@/actions/auth"
import { SESSION_COOKIE } from "@/lib/constants"

const API_BASE = process.env.API_URL || "http://localhost:8013"

/**
 * Mutations against the global catalog.
 *
 * Every call is gated by `require_platform_admin` on the backend and written
 * to the admin audit log there — these actions add no authorization of their
 * own and must not be treated as if they did.
 */
async function mutate(
  path: string,
  method: "POST" | "PATCH" | "DELETE",
  body?: unknown
): Promise<ActionResult> {
  const cookieStore = await cookies()
  const sessionCookie = cookieStore.get(SESSION_COOKIE)?.value

  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers: {
        "Content-Type": "application/json",
        ...(sessionCookie
          ? { Cookie: `${SESSION_COOKIE}=${sessionCookie}` }
          : {}),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
    })
  } catch {
    return { success: false, error: "unreachable" }
  }

  if (!res.ok) {
    // 409 carries a meaningful message (duplicate key, sport still in use), so
    // it is surfaced rather than flattened into a generic failure.
    if (res.status === 409) {
      const payload = (await res.json().catch(() => ({}))) as {
        error?: { message?: string }
      }
      return { success: false, error: payload.error?.message ?? "conflict" }
    }
    if (res.status === 403) return { success: false, error: "forbidden" }
    if (res.status === 422) return { success: false, error: "validation" }
    return { success: false, error: "unknown" }
  }

  revalidatePath("/admin", "layout")
  return { success: true }
}

// --- Sports ---

export async function createSportAction(input: {
  key: string
  name: string
  description?: string | null
  icon?: string | null
  sort_order?: number
  modules?: string[]
}): Promise<ActionResult> {
  return mutate("/api/v1/admin/catalog/sports", "POST", input)
}

export async function updateSportAction(
  sportId: string,
  input: Record<string, unknown>
): Promise<ActionResult> {
  return mutate(`/api/v1/admin/catalog/sports/${sportId}`, "PATCH", input)
}

export async function deleteSportAction(
  sportId: string
): Promise<ActionResult> {
  return mutate(`/api/v1/admin/catalog/sports/${sportId}`, "DELETE")
}

// --- Catalog units ---

export async function createUnitAction(input: {
  sport_id: string
  name: string
  symbol?: string | null
  sort_order?: number
}): Promise<ActionResult> {
  return mutate("/api/v1/admin/catalog/units", "POST", input)
}

export async function updateUnitAction(
  unitId: string,
  input: Record<string, unknown>
): Promise<ActionResult> {
  return mutate(`/api/v1/admin/catalog/units/${unitId}`, "PATCH", input)
}

export async function deleteUnitAction(unitId: string): Promise<ActionResult> {
  return mutate(`/api/v1/admin/catalog/units/${unitId}`, "DELETE")
}

// --- Catalog disciplines ---

export async function createDisciplineAction(
  input: Record<string, unknown>
): Promise<ActionResult> {
  return mutate("/api/v1/admin/catalog/disciplines", "POST", input)
}

export async function updateDisciplineAction(
  disciplineId: string,
  input: Record<string, unknown>
): Promise<ActionResult> {
  return mutate(
    `/api/v1/admin/catalog/disciplines/${disciplineId}`,
    "PATCH",
    input
  )
}

export async function deleteDisciplineAction(
  disciplineId: string
): Promise<ActionResult> {
  return mutate(`/api/v1/admin/catalog/disciplines/${disciplineId}`, "DELETE")
}
