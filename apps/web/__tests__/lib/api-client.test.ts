import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { apiFetch, ApiError } from "@/lib/api-client"

const mockFetch = vi.fn()

beforeEach(() => {
  vi.stubGlobal("fetch", mockFetch)
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe("apiFetch", () => {
  it("returns data from a successful response", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ data: { id: "1", name: "Test" } }),
    })

    const result = await apiFetch("/api/v1/club")

    expect(result).toEqual({ id: "1", name: "Test" })
  })

  it("returns the full JSON when no data key is present", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ id: "1", name: "Test" }),
    })

    const result = await apiFetch("/api/v1/something")

    expect(result).toEqual({ id: "1", name: "Test" })
  })

  it("always sends credentials: include", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ data: {} }),
    })

    await apiFetch("/api/v1/club")

    expect(mockFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({ credentials: "include" }),
    )
  })

  it("sends Content-Type: application/json by default", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ data: {} }),
    })

    await apiFetch("/api/v1/club")

    expect(mockFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        headers: expect.objectContaining({
          "Content-Type": "application/json",
        }),
      }),
    )
  })

  it("throws ApiError with correct status, code, and message on error", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: () =>
        Promise.resolve({
          error: { code: "NOT_FOUND", message: "Club not found" },
        }),
    })

    await expect(apiFetch("/api/v1/club")).rejects.toThrow(ApiError)

    try {
      await apiFetch("/api/v1/club")
    } catch (e) {
      // Need a fresh call for the assertion since the first consumed the mock
    }

    // Re-mock for a clean assertion
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: () =>
        Promise.resolve({
          error: { code: "NOT_FOUND", message: "Club not found" },
        }),
    })

    try {
      await apiFetch("/api/v1/club")
      expect.unreachable("Should have thrown")
    } catch (e) {
      expect(e).toBeInstanceOf(ApiError)
      const err = e as ApiError
      expect(err.status).toBe(404)
      expect(err.code).toBe("NOT_FOUND")
      expect(err.message).toBe("Club not found")
    }
  })

  it("falls back to defaults when error body has no error object", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: () => Promise.resolve({}),
    })

    try {
      await apiFetch("/api/v1/club")
      expect.unreachable("Should have thrown")
    } catch (e) {
      expect(e).toBeInstanceOf(ApiError)
      const err = e as ApiError
      expect(err.status).toBe(500)
      expect(err.code).toBe("UNKNOWN")
      expect(err.message).toBe("Request failed")
    }
  })

  it("handles non-JSON error body gracefully", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 502,
      json: () => Promise.reject(new Error("Not JSON")),
    })

    try {
      await apiFetch("/api/v1/club")
      expect.unreachable("Should have thrown")
    } catch (e) {
      expect(e).toBeInstanceOf(ApiError)
      const err = e as ApiError
      expect(err.status).toBe(502)
      expect(err.code).toBe("UNKNOWN")
      expect(err.message).toBe("Request failed")
    }
  })
})
