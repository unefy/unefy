import { apiCall, apiList } from "@/lib/api"
import type {
  AdminMembership,
  AdminTenant,
  AdminTenantDetail,
  AdminTenantMember,
  AdminTenantUser,
  AdminUser,
  AuditLogEntry,
  CatalogDiscipline,
  CatalogUnit,
  Sport,
  SportModule,
} from "@/lib/types/admin"

/**
 * Server-side readers for the platform admin area.
 *
 * Access is enforced by the backend (`require_platform_admin`) on every call —
 * the layout's superuser check is a UX guard, not the security boundary. If
 * these throw, the caller is not a platform admin.
 */

function query(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value))
  }
  const qs = search.toString()
  return qs ? `?${qs}` : ""
}

/**
 * The backend caps `per_page` at 100. The admin tables sort and filter on the
 * client, so they ask for the full set in one response rather than sorting a
 * single page and presenting it as the whole list.
 */
export const ADMIN_PAGE_SIZE = 100

export async function listTenants(
  options: { page?: number; search?: string; perPage?: number } = {}
) {
  return apiList<AdminTenant>(
    `/api/v1/admin/tenants${query({
      page: options.page,
      search: options.search,
      per_page: options.perPage,
    })}`
  )
}

export async function getTenant(tenantId: string) {
  return apiCall<AdminTenantDetail>(`/api/v1/admin/tenants/${tenantId}`)
}

export async function listTenantUsers(tenantId: string) {
  const { data } = await apiList<AdminTenantUser>(
    `/api/v1/admin/tenants/${tenantId}/users`
  )
  return data
}

export async function listTenantMembers(tenantId: string) {
  const { data } = await apiList<AdminTenantMember>(
    `/api/v1/admin/tenants/${tenantId}/members`
  )
  return data
}

export async function listUsers(
  options: { page?: number; search?: string; perPage?: number } = {}
) {
  return apiList<AdminUser>(
    `/api/v1/admin/users${query({
      page: options.page,
      search: options.search,
      per_page: options.perPage,
    })}`
  )
}

export async function getUser(userId: string) {
  return apiCall<AdminUser>(`/api/v1/admin/users/${userId}`)
}

export async function listUserMemberships(userId: string) {
  const { data } = await apiList<AdminMembership>(
    `/api/v1/admin/users/${userId}/memberships`
  )
  return data
}

export async function listAuditLog(
  options: {
    page?: number
    action?: string
    tenantId?: string
    perPage?: number
  } = {}
) {
  return apiList<AuditLogEntry>(
    `/api/v1/admin/audit-log${query({
      page: options.page,
      action: options.action,
      tenant_id: options.tenantId,
      per_page: options.perPage,
    })}`
  )
}

// --- Master data (platform admin) ---

export async function listSports() {
  const { data } = await apiList<Sport>("/api/v1/admin/catalog/sports")
  return data
}

export async function listSportModules() {
  const { data } = await apiList<SportModule>("/api/v1/admin/catalog/modules")
  return data
}

export async function listCatalogUnits(sportId?: string) {
  const { data } = await apiList<CatalogUnit>(
    `/api/v1/admin/catalog/units${query({ sport_id: sportId })}`
  )
  return data
}

export async function listCatalogDisciplines(
  options: {
    page?: number
    sportId?: string
    federation?: string
    category?: string
    search?: string
    perPage?: number
  } = {}
) {
  return apiList<CatalogDiscipline>(
    `/api/v1/admin/catalog/disciplines${query({
      page: options.page,
      sport_id: options.sportId,
      federation: options.federation,
      category: options.category,
      search: options.search,
      per_page: options.perPage,
    })}`
  )
}
