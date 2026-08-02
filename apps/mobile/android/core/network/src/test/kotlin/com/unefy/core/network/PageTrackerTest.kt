package com.unefy.core.network

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PageTrackerTest {

    /** Nothing has landed yet, so there is no "next" to ask for. */
    @Test
    fun `refuses to page before the first page has arrived`() {
        assertFalse(PageTracker().start())
    }

    @Test
    fun `pages while the backend says there is more`() {
        val tracker = PageTracker()
        tracker.advance(meta(page = 1, totalPages = 3))

        assertTrue(tracker.start())
        assertEquals(2, tracker.next)
        tracker.advance(meta(page = 2, totalPages = 3))

        assertTrue(tracker.start())
        assertEquals(3, tracker.next)
        tracker.advance(meta(page = 3, totalPages = 3))

        assertFalse(tracker.start())
    }

    /**
     * The scroll listener asks on position, not on state, so it asks again long
     * before the page it already triggered has come back.
     */
    @Test
    fun `a second ask while a page is in flight is refused`() {
        val tracker = PageTracker()
        tracker.advance(meta(page = 1, totalPages = 5))

        assertTrue(tracker.start())
        assertFalse(tracker.start())
        assertFalse(tracker.start())
    }

    /** A failed page must be retried, not skipped. */
    @Test
    fun `a failure leaves the same page next in line`() {
        val tracker = PageTracker()
        tracker.advance(meta(page = 1, totalPages = 5))

        assertTrue(tracker.start())
        assertEquals(2, tracker.next)
        tracker.fail()

        assertTrue(tracker.start())
        assertEquals(2, tracker.next)
    }

    @Test
    fun `reset goes back to the first page and stops paging`() {
        val tracker = PageTracker()
        tracker.advance(meta(page = 4, totalPages = 9))
        tracker.reset()

        assertEquals(1, tracker.next)
        assertFalse(tracker.start())
    }

    /**
     * A backend that stops sending meta must stop the paging, not spin it. The
     * alternative — assuming another page might exist — asks forever.
     */
    @Test
    fun `a missing meta ends the paging`() {
        val tracker = PageTracker()
        tracker.advance(null)

        assertFalse(tracker.start())
    }

    @Test
    fun `hasNextPage reads the meta the backend sent`() {
        assertTrue(meta(page = 1, totalPages = 2).hasNextPage())
        assertFalse(meta(page = 2, totalPages = 2).hasNextPage())
        assertFalse(null.hasNextPage())
    }

    private fun meta(page: Int, totalPages: Int) =
        ApiMeta(total = totalPages * 50, page = page, perPage = 50, totalPages = totalPages)
}
