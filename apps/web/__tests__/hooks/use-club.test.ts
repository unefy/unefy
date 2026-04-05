import { describe, it, expect, vi, beforeEach } from "vitest"
import { renderHook, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createElement } from "react"
import { useUpdateClub, clubKeys } from "@/hooks/use-club"

vi.mock("@/lib/api-client", () => ({
  apiFetch: vi.fn(),
}))

import { apiFetch } from "@/lib/api-client"

const mockedApiFetch = vi.mocked(apiFetch)

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  function Wrapper({ children }: { children: React.ReactNode }) {
    return createElement(QueryClientProvider, { client: queryClient }, children)
  }
  return Wrapper
}

describe("useUpdateClub", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("sends a PATCH request with the provided data", async () => {
    const updatedClub = { id: "1", name: "Updated Club" }
    mockedApiFetch.mockResolvedValueOnce({ data: updatedClub })

    const { result } = renderHook(() => useUpdateClub(), {
      wrapper: createWrapper(),
    })

    result.current.mutate({ name: "Updated Club" })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(mockedApiFetch).toHaveBeenCalledWith("/api/v1/club", {
      method: "PATCH",
      body: JSON.stringify({ name: "Updated Club" }),
    })
  })

  it("converts empty strings to null", async () => {
    const updatedClub = { id: "1", name: "Club", email: null }
    mockedApiFetch.mockResolvedValueOnce({ data: updatedClub })

    const { result } = renderHook(() => useUpdateClub(), {
      wrapper: createWrapper(),
    })

    result.current.mutate({ name: "Club", email: "" as string | null })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(mockedApiFetch).toHaveBeenCalledWith("/api/v1/club", {
      method: "PATCH",
      body: JSON.stringify({ name: "Club", email: null }),
    })
  })

  it("preserves boolean values (does not convert false to null)", async () => {
    const updatedClub = { id: "1", is_nonprofit: false }
    mockedApiFetch.mockResolvedValueOnce({ data: updatedClub })

    const { result } = renderHook(() => useUpdateClub(), {
      wrapper: createWrapper(),
    })

    result.current.mutate({ is_nonprofit: false })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(mockedApiFetch).toHaveBeenCalledWith("/api/v1/club", {
      method: "PATCH",
      body: JSON.stringify({ is_nonprofit: false }),
    })
  })

  it("updates query cache on success with unwrapped data", async () => {
    const updatedClub = { id: "1", name: "New Name" }
    mockedApiFetch.mockResolvedValueOnce({ data: updatedClub })

    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    })

    const wrapper = ({ children }: { children: React.ReactNode }) =>
      createElement(QueryClientProvider, { client: queryClient }, children)

    const { result } = renderHook(() => useUpdateClub(), { wrapper })

    result.current.mutate({ name: "New Name" })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    // Cache should contain the unwrapped club, not the envelope
    expect(queryClient.getQueryData(clubKeys.detail())).toEqual(updatedClub)
  })
})
