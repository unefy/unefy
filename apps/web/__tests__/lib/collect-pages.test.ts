import { describe, expect, it, vi } from "vitest"

import { MAX_COLLECTED_PAGES, collectPages } from "@/lib/api"

function pager(total: number, perPage = 100) {
  const rows = Array.from({ length: total }, (_, index) => index + 1)
  return vi.fn(async (page: number) => ({
    data: rows.slice((page - 1) * perPage, page * perPage),
    meta: {
      total,
      page,
      per_page: perPage,
      total_pages: Math.max(1, Math.ceil(total / perPage)),
    },
  }))
}

describe("collectPages", () => {
  it("returns everything past the first page", async () => {
    const fetchPage = pager(240)
    const result = await collectPages(fetchPage)

    // The bug this exists for: member 101 onwards used to be invisible.
    expect(result.data).toHaveLength(240)
    expect(result.data.at(-1)).toBe(240)
    expect(result.total).toBe(240)
    expect(result.truncated).toBe(false)
    expect(fetchPage).toHaveBeenCalledTimes(3)
  })

  it("asks once when one page is all there is", async () => {
    const fetchPage = pager(12)
    const result = await collectPages(fetchPage)

    expect(result.data).toHaveLength(12)
    expect(fetchPage).toHaveBeenCalledTimes(1)
  })

  it("handles an empty club without a second request", async () => {
    const fetchPage = pager(0)
    const result = await collectPages(fetchPage)

    expect(result.data).toEqual([])
    expect(result.total).toBe(0)
    expect(fetchPage).toHaveBeenCalledTimes(1)
  })

  it("stops at the bound and says so", async () => {
    const fetchPage = pager(100 * (MAX_COLLECTED_PAGES + 5))
    const result = await collectPages(fetchPage)

    expect(fetchPage).toHaveBeenCalledTimes(MAX_COLLECTED_PAGES)
    expect(result.truncated).toBe(true)
    // The count still reports the whole set — the screen may show less, but it
    // must not lie about how much there is.
    expect(result.total).toBe(100 * (MAX_COLLECTED_PAGES + 5))
  })

  it("stops early when the server runs out before meta promised", async () => {
    const fetchPage = vi.fn(async (page: number) => ({
      data: page === 1 ? [1, 2, 3] : [],
      meta: { total: 999, page, per_page: 100, total_pages: 10 },
    }))
    const result = await collectPages(fetchPage)

    expect(result.data).toEqual([1, 2, 3])
    expect(fetchPage).toHaveBeenCalledTimes(2)
  })
})
