"use server"

import { revalidatePath } from "next/cache"
import { z } from "zod"

import { apiCall, ApiError } from "@/lib/api"
import { parseRuleForm, revokeReasonSchema } from "@/lib/shooting-schema"
import type {
  ProofEvaluation,
  ShootingCertificate,
  ShootingRecordDetail,
  ShootingRule,
} from "@/lib/types/shooting"

export type ActionResult<T = unknown> =
  { success: true; data?: T } | { success: false; error: string }

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

function refresh() {
  revalidatePath("/shooting")
  revalidatePath("/shooting/rules")
}

// --- Rules ---

export async function createRuleAction(
  _prev: ActionResult | undefined,
  formData: FormData
): Promise<ActionResult<ShootingRule>> {
  const parsed = parseRuleForm(formData)
  if (!parsed.success) return { success: false, error: "validation" }

  try {
    const created = await apiCall<ShootingRule>("/api/v1/modules/shooting/rules", {
      method: "POST",
      body: JSON.stringify(parsed.data),
    })
    refresh()
    return { success: true, data: created }
  } catch (error) {
    return toError(error)
  }
}

export async function updateRuleAction(
  ruleId: string,
  _prev: ActionResult | undefined,
  formData: FormData
): Promise<ActionResult<ShootingRule>> {
  if (!uuid.safeParse(ruleId).success) {
    return { success: false, error: "validation" }
  }
  const parsed = parseRuleForm(formData)
  if (!parsed.success) return { success: false, error: "validation" }

  // `rule_key` is deliberately not sent — issued certificates reference it,
  // and the backend refuses to change it anyway.
  const payload = {
    label: parsed.data.label,
    window_months: parsed.data.window_months,
    min_total_days: parsed.data.min_total_days,
    min_distinct_months: parsed.data.min_distinct_months,
  }
  try {
    const updated = await apiCall<ShootingRule>(
      `/api/v1/modules/shooting/rules/${ruleId}`,
      { method: "PATCH", body: JSON.stringify(payload) }
    )
    refresh()
    return { success: true, data: updated }
  } catch (error) {
    return toError(error)
  }
}

export async function deleteRuleAction(ruleId: string): Promise<ActionResult> {
  if (!uuid.safeParse(ruleId).success) {
    return { success: false, error: "validation" }
  }
  try {
    await apiCall(`/api/v1/modules/shooting/rules/${ruleId}`, {
      method: "DELETE",
    })
  } catch (error) {
    return toError(error)
  }
  refresh()
  return { success: true }
}

// --- Evaluation & certificates ---

export async function evaluateProofAction(
  memberId: string,
  ruleKey: string
): Promise<ActionResult<ProofEvaluation>> {
  if (!uuid.safeParse(memberId).success || !ruleKey.trim()) {
    return { success: false, error: "validation" }
  }
  try {
    const evaluation = await apiCall<ProofEvaluation>(
      `/api/v1/modules/shooting/proof/${memberId}?rule_key=${encodeURIComponent(ruleKey)}`
    )
    return { success: true, data: evaluation }
  } catch (error) {
    return toError(error)
  }
}

export async function issueCertificateAction(
  memberId: string,
  ruleKey: string
): Promise<ActionResult<ShootingCertificate>> {
  if (!uuid.safeParse(memberId).success || !ruleKey.trim()) {
    return { success: false, error: "validation" }
  }
  try {
    const certificate = await apiCall<ShootingCertificate>(
      "/api/v1/modules/shooting/certificates",
      {
        method: "POST",
        body: JSON.stringify({ member_id: memberId, rule_key: ruleKey }),
      }
    )
    refresh()
    return { success: true, data: certificate }
  } catch (error) {
    return toError(error)
  }
}

export async function revokeCertificateAction(
  certificateId: string,
  reason: string
): Promise<ActionResult> {
  const parsed = revokeReasonSchema.safeParse(reason)
  if (!uuid.safeParse(certificateId).success || !parsed.success) {
    return { success: false, error: "validation" }
  }
  try {
    await apiCall(
      `/api/v1/modules/shooting/certificates/${certificateId}/revoke`,
      { method: "POST", body: JSON.stringify({ reason: parsed.data }) }
    )
  } catch (error) {
    return toError(error)
  }
  refresh()
  return { success: true }
}

// --- Record details ---

/**
 * What somebody shot, written onto one attendance record.
 *
 * Upsert: the first save creates the row. Fields left empty are sent as null
 * rather than omitted, so clearing a wrong entry is possible — an entry form
 * whose values can only ever be added to is a trap.
 *
 * Guest rows are refused by the server (`GUEST_RECORD`): a guest counts towards
 * no §14 proof, so a discipline on one would be decoration. The UI does not
 * offer it, and this maps the refusal to a message anyway — the two must not
 * drift apart silently.
 */
export async function saveRecordDetailAction(
  sessionId: string,
  recordId: string,
  input: {
    club_discipline_id: string | null
    weapon_category: string | null
    rounds_fired: number | null
  }
): Promise<ActionResult<ShootingRecordDetail>> {
  if (!uuid.safeParse(recordId).success) return { success: false, error: "validation" }

  try {
    const saved = await apiCall<ShootingRecordDetail>(
      `/api/v1/modules/shooting/records/${recordId}`,
      { method: "PATCH", body: JSON.stringify(input) }
    )
    revalidatePath(`/attendance/${sessionId}`)
    return { success: true, data: saved }
  } catch (error) {
    return toError(error)
  }
}
