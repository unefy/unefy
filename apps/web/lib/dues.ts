import { apiList } from "@/lib/api"
import type { MyDue } from "@/lib/types/due"

/** The caller's own dues — member resolution happens in the backend. */
export async function listMyDues() {
  return (await apiList<MyDue>("/api/v1/dues/me?per_page=100")).data
}
