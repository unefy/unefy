"use server"

import { revalidatePath } from "next/cache"
import { z } from "zod"

import { apiCall, ApiError } from "@/lib/api"

export type ActionResult<T = unknown> =
  { success: true; data?: T } | { success: false; error: string }

/**
 * Maps a backend failure onto a translation key.
 *
 * The backend's own message is not surfaced: it is English and written for
 * developers. The codes it returns are stable enough to translate against.
 */
function toError<T = unknown>(error: unknown): ActionResult<T> {
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
const role = z.enum(["owner", "admin", "board", "member"])

export async function inviteMemberAction(
  memberId: string,
  requestedRole: string = "member"
): Promise<ActionResult<{ accept_url: string }>> {
  const parsed = z
    .object({ member_id: uuid, role })
    .safeParse({ member_id: memberId, role: requestedRole })
  if (!parsed.success) return { success: false, error: "validation" }

  let invitation: { accept_url: string }
  try {
    // The address deliberately is not sent — the backend takes it from the
    // member record, so a tampered request cannot bind a stranger's account.
    invitation = await apiCall<{ accept_url: string }>(
      "/api/v1/club/access/invitations",
      {
        method: "POST",
        body: JSON.stringify({
          member_id: parsed.data.member_id,
          role: parsed.data.role,
        }),
      }
    )
  } catch (error) {
    return toError(error)
  }

  revalidatePath(`/members/${memberId}`)
  revalidatePath("/members")
  // The link exists only in this response — the backend stores a hash. It is
  // handed to the UI once so the inviter can pass it on by hand when the
  // club's mail is not set up.
  return { success: true, data: { accept_url: invitation.accept_url } }
}

export async function linkMemberAction(
  memberId: string,
  userId: string
): Promise<ActionResult> {
  const parsed = z
    .object({ member_id: uuid, user_id: uuid })
    .safeParse({ member_id: memberId, user_id: userId })
  if (!parsed.success) return { success: false, error: "validation" }

  try {
    await apiCall("/api/v1/club/access/links", {
      method: "POST",
      body: JSON.stringify(parsed.data),
    })
  } catch (error) {
    return toError(error)
  }

  revalidatePath(`/members/${memberId}`)
  revalidatePath("/members")
  return { success: true }
}

export async function unlinkMemberAction(memberId: string): Promise<ActionResult> {
  if (!uuid.safeParse(memberId).success) {
    return { success: false, error: "validation" }
  }

  try {
    await apiCall(`/api/v1/club/access/links/${memberId}`, { method: "DELETE" })
  } catch (error) {
    return toError(error)
  }

  revalidatePath(`/members/${memberId}`)
  revalidatePath("/members")
  return { success: true }
}

export async function revokeInvitationAction(
  invitationId: string,
  memberId?: string
): Promise<ActionResult> {
  if (!uuid.safeParse(invitationId).success) {
    return { success: false, error: "validation" }
  }

  try {
    await apiCall(`/api/v1/club/access/invitations/${invitationId}`, {
      method: "DELETE",
    })
  } catch (error) {
    return toError(error)
  }

  if (memberId) revalidatePath(`/members/${memberId}`)
  revalidatePath("/members")
  return { success: true }
}

export async function setAccessActiveAction(
  userId: string,
  isActive: boolean,
  memberId?: string
): Promise<ActionResult> {
  if (!uuid.safeParse(userId).success) {
    return { success: false, error: "validation" }
  }

  try {
    await apiCall(`/api/v1/club/access/members/${userId}/active`, {
      method: "PATCH",
      body: JSON.stringify({ is_active: isActive }),
    })
  } catch (error) {
    return toError(error)
  }

  if (memberId) revalidatePath(`/members/${memberId}`)
  revalidatePath("/members")
  return { success: true }
}

export async function setAccessRoleAction(
  userId: string,
  requestedRole: string,
  memberId?: string
): Promise<ActionResult> {
  const parsed = z
    .object({ user_id: uuid, role })
    .safeParse({ user_id: userId, role: requestedRole })
  if (!parsed.success) return { success: false, error: "validation" }

  try {
    await apiCall(`/api/v1/club/access/members/${parsed.data.user_id}`, {
      method: "PATCH",
      body: JSON.stringify({ role: parsed.data.role }),
    })
  } catch (error) {
    return toError(error)
  }

  if (memberId) revalidatePath(`/members/${memberId}`)
  revalidatePath("/members")
  return { success: true }
}
