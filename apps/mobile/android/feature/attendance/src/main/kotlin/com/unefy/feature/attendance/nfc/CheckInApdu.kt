package com.unefy.feature.attendance.nfc

/**
 * The wire format between a member's phone and a supervisor's, over NFC.
 *
 * Both halves of the exchange live in this one file on purpose: a card and a
 * reader that disagree by a byte fail with nothing on screen to explain it, and
 * the two sides are written weeks apart.
 *
 * What travels is the same rotating code the QR carries — same HMAC, same
 * counter, same single-use rule. NFC is a transport, not a second scheme, so
 * the backend does not change and neither does the security argument.
 *
 * The exchange is two commands:
 *
 * ```
 * reader → card   SELECT AID              00 A4 04 00 06 F0 75 6E 65 66 79 00
 * card   → reader <code bytes> 90 00
 * reader → card   RESULT <status>         80 10 00 00 01 <status>
 * card   → reader 90 00
 * ```
 *
 * The second command is what makes this worth doing. Without it the member's
 * phone would know it had been read and nothing more; with it, it knows how the
 * check-in went and can say so in the same second — which is the entire reason
 * NFC was added next to a QR that already worked.
 */
object CheckInApdu {

    /**
     * Proprietary AID, `F0` + "unefy".
     *
     * The `F0` prefix is the range ISO/IEC 7816-5 reserves for applications
     * that are not registered with an authority, which is what this is.
     */
    val AID: ByteArray = byteArrayOf(0xF0.toByte(), 0x75, 0x6E, 0x65, 0x66, 0x79)

    /** What the reader sends first. Android routes it to us by the AID inside. */
    val SELECT: ByteArray = byteArrayOf(0x00, 0xA4.toByte(), 0x04, 0x00, AID.size.toByte()) +
        AID + byteArrayOf(0x00)

    private const val CLA_PROPRIETARY = 0x80.toByte()
    private const val INS_RESULT = 0x10.toByte()

    /** Success, and the only status the card treats as "you are checked in". */
    val SW_OK: ByteArray = byteArrayOf(0x90.toByte(), 0x00)

    /** The card has no seed yet, so it has nothing to offer. */
    val SW_NOT_READY: ByteArray = byteArrayOf(0x69, 0x85.toByte())

    /** Anything the card did not understand. */
    val SW_UNKNOWN: ByteArray = byteArrayOf(0x6D, 0x00)

    /** How the check-in went, as one byte the reader hands back. */
    enum class Outcome(val code: Byte) {
        RECORDED(0x00),

        /** Taken, but held on the reader's device until it has a connection. */
        QUEUED(0x01),

        ALREADY_PRESENT(0x02),

        REJECTED(0x03),
        ;

        companion object {
            fun from(code: Byte): Outcome = entries.firstOrNull { it.code == code } ?: REJECTED
        }
    }

    fun resultCommand(outcome: Outcome): ByteArray =
        byteArrayOf(CLA_PROPRIETARY, INS_RESULT, 0x00, 0x00, 0x01, outcome.code)

    fun isSelect(command: ByteArray): Boolean =
        command.size >= SELECT_HEADER && command[0] == 0x00.toByte() &&
            command[1] == 0xA4.toByte() && command.copyOfRange(5, 5 + AID.size).contentEquals(AID)

    fun outcomeOrNull(command: ByteArray): Outcome? =
        if (command.size == RESULT_LENGTH &&
            command[0] == CLA_PROPRIETARY &&
            command[1] == INS_RESULT
        ) {
            Outcome.from(command[RESULT_LENGTH - 1])
        } else {
            null
        }

    private const val SELECT_HEADER = 5 + 6
    private const val RESULT_LENGTH = 6
}
