package com.unefy.core.network

/**
 * How far a paged list has got, and whether it may ask for another page.
 *
 * Every list screen needs the same three pieces of bookkeeping — the next page
 * number, whether one exists, and whether a request is already out — and gets
 * them wrong in the same three ways: paging past the end, firing the same page
 * twice because the scroll listener asked again, and paging on after a failure.
 *
 * Not thread-safe, and does not need to be: it is touched only from a
 * ViewModel's main-dispatcher coroutines.
 */
class PageTracker {

    /** The page [start] has cleared the caller to fetch. */
    var next: Int = 1
        private set

    private var hasMore = false
    private var inFlight = false

    /**
     * Whether to fetch [next] now. False when a page is already in flight, when
     * the last page has been seen, or before the first page has landed — a
     * scroll listener fires on position alone and knows none of that.
     */
    fun start(): Boolean {
        if (inFlight || !hasMore) return false
        inFlight = true
        return true
    }

    /** Records a page that arrived, from the meta the backend sent with it. */
    fun advance(meta: ApiMeta?) {
        next = (meta?.page ?: next) + 1
        hasMore = meta.hasNextPage()
        inFlight = false
    }

    /**
     * Records a page that did not arrive. [next] does not move, so a retry asks
     * for the same page rather than skipping it.
     */
    fun fail() {
        inFlight = false
    }

    /** Back to the start, for a reload or a changed search term. */
    fun reset() {
        next = 1
        hasMore = false
        inFlight = false
    }
}
