import { cookies } from "next/headers"

import { SESSION_COOKIE } from "@/lib/constants"

const API_BASE = process.env.API_URL || "http://localhost:8013"

/** Consistent response envelope used by the backend. */
export type ApiEnvelope<T> = {
  data?: T
  error?: { code: string; message: string }
  meta?: PaginationMeta
}

export type PaginationMeta = {
  total: number
  page: number
  per_page: number
  total_pages: number
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string
  ) {
    super(`API ${status}: ${code}`)
    this.name = "ApiError"
  }
}

/**
 * Server-side call to the backend, forwarding the browser's session cookie so
 * the backend can resolve the user. Mirrors a rotated session cookie back to
 * the browser.
 *
 * Only usable from Server Components / Server Actions — it reads `cookies()`.
 */
export async function apiCall<T>(
  path: string,
  init: RequestInit = {}
): Promise<T> {
  return (await apiRequest<T>(path, init)).data as T
}

/**
 * Like `apiCall`, but keeps the `meta` envelope that paginated list endpoints
 * return — `apiCall` discards it.
 */
export async function apiList<T>(
  path: string,
  init: RequestInit = {}
): Promise<{ data: T[]; meta: PaginationMeta }> {
  const body = await apiRequest<T[]>(path, init)
  const data = body.data ?? []
  return {
    data,
    meta: body.meta ?? {
      total: data.length,
      page: 1,
      per_page: data.length,
      total_pages: 1,
    },
  }
}

async function apiRequest<T>(
  path: string,
  init: RequestInit = {}
): Promise<ApiEnvelope<T>> {
  const cookieStore = await cookies()
  const sessionCookie = cookieStore.get(SESSION_COOKIE)?.value

  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(sessionCookie
        ? { Cookie: `${SESSION_COOKIE}=${sessionCookie}` }
        : {}),
      ...init.headers,
    },
    cache: "no-store",
  })

  const setCookieHeader = res.headers.get("set-cookie")
  if (setCookieHeader) {
    const match = setCookieHeader.match(new RegExp(`${SESSION_COOKIE}=([^;]+)`))
    // Backend session tokens are URL-safe base64 — accept nothing else.
    if (match && /^[A-Za-z0-9_-]{20,256}$/.test(match[1])) {
      cookieStore.set(SESSION_COOKIE, match[1], {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        path: "/",
        maxAge: 60 * 60 * 24 * 7,
      })
    }
  }

  const body = (await res.json().catch(() => ({}))) as ApiEnvelope<T>

  if (!res.ok) {
    throw new ApiError(res.status, body.error?.code ?? "unknown")
  }

  return body
}
