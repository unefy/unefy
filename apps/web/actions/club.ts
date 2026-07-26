"use server"

import { ApiError, apiCall } from "@/lib/api"

export type DeleteClubResult =
  | { success: true }
  | { success: false; error: string }

export async function deleteClubAction(): Promise<DeleteClubResult> {
  try {
    await apiCall("/api/v1/club", { method: "DELETE" })
    return { success: true }
  } catch (e) {
    if (e instanceof ApiError) {
      let code = "unknown"
      try {
        const body = JSON.parse(e.message) as { error?: { code?: string } }
        if (typeof body.error?.code === "string") code = body.error.code
      } catch {
        // non-JSON body — keep generic code so backend details never reach the UI
      }
      return { success: false, error: code }
    }
    return { success: false, error: "unknown" }
  }
}
