import { apiList } from "@/lib/api"

export type PublicSport = {
  id: string
  key: string
  name: string
  description: string | null
  icon: string | null
}

/**
 * Active sports for the onboarding picker.
 *
 * Backed by `/api/v1/sports`, which authenticates but does not require a
 * tenant — the caller is mid-onboarding and does not have one yet.
 */
export async function listAvailableSports() {
  const { data } = await apiList<PublicSport>("/api/v1/sports")
  return data
}
