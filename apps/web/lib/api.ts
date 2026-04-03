import { cookies } from "next/headers"

const API_BASE = process.env.API_URL || "http://localhost:8008"
const COOKIE_NAME = "unefy_session"

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
    this.name = "ApiError"
  }
}

/**
 * Server-side API client. Forwards the session cookie to the backend.
 */
export async function apiCall<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const cookieStore = await cookies()
  const sessionCookie = cookieStore.get(COOKIE_NAME)?.value

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(sessionCookie ? { Cookie: `${COOKIE_NAME}=${sessionCookie}` } : {}),
      ...options?.headers,
    },
  })

  if (!res.ok) {
    const body = await res.text()
    throw new ApiError(res.status, body)
  }

  return res.json() as Promise<T>
}
