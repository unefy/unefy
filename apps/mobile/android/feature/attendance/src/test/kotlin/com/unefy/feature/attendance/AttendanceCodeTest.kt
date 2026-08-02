package com.unefy.feature.attendance

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test

/**
 * The app and the backend must compute the identical code, or check-in never
 * works. These vectors were produced by the real Python implementation
 * (`backend/app/services/attendance_code.py`) and pasted in verbatim.
 *
 * Regenerate after any change to the code format, on both sides:
 *
 * ```
 * uv run python -c "from app.services.attendance_code import *; ..."
 * ```
 *
 * A hand-written expectation would only prove this file agrees with itself.
 */
class AttendanceCodeTest {

    private val tenant = "11111111-1111-1111-1111-111111111111"

    @Test
    fun `matches the backend for a mid-period timestamp`() {
        assertEquals(
            "uf1.AAAAAAAAAAAAAAAA.59448240.VW54OV2ZM3OO4N6X",
            AttendanceCode.build(
                seed = "DRNQW4ABVQPCVEXQQWBUVKVBSRZH6XCMZ2I7CNYGQHJU6H4FLYAA",
                memberRef = "AAAAAAAAAAAAAAAA",
                tenantId = tenant,
                counter = 59_448_240L,
            ),
        )
    }

    @Test
    fun `matches the backend for the next window`() {
        // One counter later, same seed: the whole MAC has to change, which is
        // what makes a photographed code worthless 30 seconds on.
        assertEquals(
            "uf1.AAAAAAAAAAAAAAAA.59448241.D6CJQJJLVKFHCNRA",
            AttendanceCode.build(
                seed = "DRNQW4ABVQPCVEXQQWBUVKVBSRZH6XCMZ2I7CNYGQHJU6H4FLYAA",
                memberRef = "AAAAAAAAAAAAAAAA",
                tenantId = tenant,
                counter = 59_448_241L,
            ),
        )
    }

    @Test
    fun `matches the backend at the epoch`() {
        // Counter 0 — the boundary a division-based counter is most likely to
        // get wrong.
        assertEquals(
            "uf1.AAAAAAAAAAAAAAAA.0.THYC6SGKSSSQHWQW",
            AttendanceCode.build(
                seed = "75IIS43MX46ZGTEBSJ3U2Q7KYFHHVDW7MCVHVRW6ETDFO63RFK7Q",
                memberRef = "AAAAAAAAAAAAAAAA",
                tenantId = tenant,
                counter = 0L,
            ),
        )
    }

    @Test
    fun `matches the backend for a short seed and a mixed ref`() {
        // A seed that is not itself a Base32 digest, and a ref using the whole
        // alphabet: proves the MAC treats both as plain strings.
        assertEquals(
            "uf1.MNOPQRSTUVWX2345.999.A4N2AWX3A62D3TSM",
            AttendanceCode.build(
                seed = "SEEDVALUE12345",
                memberRef = "MNOPQRSTUVWX2345",
                tenantId = tenant,
                counter = 999L,
            ),
        )
    }

    @Test
    fun `a different tenant produces a different code`() {
        val mine = AttendanceCode.build("SEEDVALUE12345", "MNOPQRSTUVWX2345", tenant, 999L)
        val theirs = AttendanceCode.build(
            "SEEDVALUE12345",
            "MNOPQRSTUVWX2345",
            "44444444-4444-4444-4444-444444444444",
            999L,
        )

        assertNotEquals(mine, theirs)
    }

    @Test
    fun `mac is always sixteen base32 characters`() {
        // Ten bytes is exactly sixteen characters. A shorter one would mean the
        // encoder dropped a group and the backend's regex would reject it.
        repeat(50) { index ->
            val mac = AttendanceCode.build("seed-$index", "AAAAAAAAAAAAAAAA", tenant, index.toLong())
                .substringAfterLast('.')
            assertEquals(16, mac.length)
            assertEquals(mac, mac.uppercase())
            assertEquals("", mac.filter { it !in "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567" })
        }
    }

    @Test
    fun `counter advances once per interval`() {
        assertEquals(59_448_240L, AttendanceCode.counterFor(1_783_447_200L))
        assertEquals(59_448_240L, AttendanceCode.counterFor(1_783_447_229L))
        assertEquals(59_448_241L, AttendanceCode.counterFor(1_783_447_230L))
    }

    @Test
    fun `countdown runs from the interval down to one`() {
        assertEquals(30L, AttendanceCode.secondsUntilNextCode(1_783_447_200L))
        assertEquals(1L, AttendanceCode.secondsUntilNextCode(1_783_447_229L))
        assertEquals(30L, AttendanceCode.secondsUntilNextCode(1_783_447_230L))
    }
}
