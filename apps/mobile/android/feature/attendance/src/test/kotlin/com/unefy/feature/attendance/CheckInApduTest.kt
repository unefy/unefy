package com.unefy.feature.attendance

import com.unefy.feature.attendance.nfc.CheckInApdu
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The card and the reader agree byte for byte, or a tap fails with nothing on
 * screen to explain it. These are the bytes, written out rather than derived,
 * so a change to the format has to be a deliberate edit here too.
 */
class CheckInApduTest {

    @Test
    fun `select carries the aid in the shape a reader sends it`() {
        // 00 A4 04 00 06 F0 75 6E 65 66 79 00 — CLA INS P1 P2 Lc, AID, Le.
        assertArrayEquals(
            byteArrayOf(
                0x00, 0xA4.toByte(), 0x04, 0x00, 0x06,
                0xF0.toByte(), 0x75, 0x6E, 0x65, 0x66, 0x79,
                0x00,
            ),
            CheckInApdu.SELECT,
        )
    }

    @Test
    fun `the aid matches what the manifest registers`() {
        // The XML cannot reference the constant, so the two are checked here.
        assertEquals("F0756E656679", CheckInApdu.AID.joinToString("") { "%02X".format(it) })
    }

    @Test
    fun `the card recognises the reader's select`() {
        assertTrue(CheckInApdu.isSelect(CheckInApdu.SELECT))
    }

    @Test
    fun `a select for somebody else's aid is not ours`() {
        val other = CheckInApdu.SELECT.copyOf().also { it[5] = 0xA0.toByte() }

        assertFalse(CheckInApdu.isSelect(other))
    }

    @Test
    fun `a truncated command is not mistaken for a select`() {
        // A tap that moved mid-exchange delivers exactly this.
        assertFalse(CheckInApdu.isSelect(byteArrayOf(0x00, 0xA4.toByte(), 0x04)))
    }

    @Test
    fun `every outcome survives the round trip`() {
        CheckInApdu.Outcome.entries.forEach { outcome ->
            val command = CheckInApdu.resultCommand(outcome)
            assertEquals(outcome, CheckInApdu.outcomeOrNull(command))
        }
    }

    @Test
    fun `a select is not read as an outcome`() {
        assertNull(CheckInApdu.outcomeOrNull(CheckInApdu.SELECT))
    }

    @Test
    fun `an unknown status byte is treated as a refusal`() {
        // Fail closed: a byte this version does not know must not read as
        // "checked in" on the member's phone.
        val command = CheckInApdu.resultCommand(CheckInApdu.Outcome.RECORDED)
            .copyOf().also { it[it.size - 1] = 0x7F }

        assertEquals(CheckInApdu.Outcome.REJECTED, CheckInApdu.outcomeOrNull(command))
    }

    @Test
    fun `status words are the two bytes a reader looks for`() {
        assertArrayEquals(byteArrayOf(0x90.toByte(), 0x00), CheckInApdu.SW_OK)
        assertEquals(2, CheckInApdu.SW_NOT_READY.size)
        assertFalse(CheckInApdu.SW_NOT_READY.contentEquals(CheckInApdu.SW_OK))
    }
}
