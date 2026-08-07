package com.unefy.app.di

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * What a person types into the server field, and what Ktor can be handed.
 *
 * The two are not the same thing, and every difference here comes from a way a
 * hostname is normally written down rather than from a way a URL is specified.
 */
class ServerUrlStoreTest {

    @Test
    fun `a bare hostname becomes https`() {
        // What is on a club's letterhead, and what somebody will type.
        assertEquals("https://verein.example.org", ServerUrlStore.normalise("verein.example.org"))
    }

    @Test
    fun `plain http is left alone`() {
        // A self-hosted server on the club's own network may have no
        // certificate. Silently upgrading it would make it unreachable with no
        // hint as to why.
        assertEquals("http://192.168.1.10:8000", ServerUrlStore.normalise("http://192.168.1.10:8000"))
    }

    @Test
    fun `a trailing slash is dropped`() {
        // Every request path starts with one, so keeping this doubles it up and
        // the server answers 404 for everything.
        assertEquals("https://test.unefy.app", ServerUrlStore.normalise("https://test.unefy.app/"))
    }

    @Test
    fun `surrounding whitespace is dropped`() {
        // Pasted addresses arrive with it far more often than not.
        assertEquals("https://test.unefy.app", ServerUrlStore.normalise("  test.unefy.app  "))
    }

    @Test
    fun `nonsense is rejected rather than saved`() {
        assertFalse("empty", ServerUrlStore.isValid(""))
        assertFalse("only a scheme", ServerUrlStore.isValid("https://"))
        assertFalse("only a port", ServerUrlStore.isValid(":8000"))
        assertFalse("a sentence", ServerUrlStore.isValid("unser server bitte"))
    }

    @Test
    fun `the shapes people actually type are accepted`() {
        assertTrue(ServerUrlStore.isValid("test.unefy.app"))
        assertTrue(ServerUrlStore.isValid("https://test.unefy.app"))
        assertTrue(ServerUrlStore.isValid("http://192.168.1.10:8013"))
        assertTrue(ServerUrlStore.isValid("verein.example.org/unefy"))
    }
}
