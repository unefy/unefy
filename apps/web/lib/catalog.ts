import { apiCall } from "@/lib/api"
import type { ClubDiscipline } from "@/lib/types/shooting"

/**
 * The club's own catalogue.
 *
 * Disciplines belong to every sport — a running club has 5000 m where a
 * shooting club has Luftgewehr — so this reader sits outside the shooting
 * module even though the type still lives next to it. The endpoint carries no
 * module gate either.
 */
export async function listClubDisciplines() {
  return apiCall<ClubDiscipline[]>("/api/v1/club-disciplines")
}
