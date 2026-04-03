/**
 * Client-side API helper for TanStack Query.
 * Runs in the browser — sends session cookie via credentials: "include".
 *
 * For server-side fetching (Server Components), use lib/api.ts instead.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8008"

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message)
    this.name = "ApiError"
  }
}

export async function apiFetch<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  })

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new ApiError(
      res.status,
      body.error?.code || "UNKNOWN",
      body.error?.message || "Request failed",
    )
  }

  const json = await res.json()
  return json.data !== undefined ? json.data : json
}
