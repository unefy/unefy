package com.unefy.feature.attendance

import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

/**
 * The member's rotating check-in code, computed on the device.
 *
 * A mirror of `backend/app/services/attendance_code.py`. The two must agree
 * byte for byte or nothing verifies, so the format is spelled out here rather
 * than assembled from helpers:
 *
 * ```
 * uf1.<member_ref>.<counter>.<mac>
 *   counter = unix_seconds / 30
 *   mac     = Base32(HMAC-SHA256(seed, "<tenant>|<member_ref>|<counter>")[0..10])
 * ```
 *
 * Offline by design. The seed lasts a day, the arithmetic needs no network, and
 * shooting ranges are usually in basements with no signal — a code that needed
 * a request to produce would be a code that fails exactly where it is used.
 *
 * Deliberately free of Android imports: this is the piece that has to be tested
 * against the backend's own vectors, and a JVM test is the cheap way to do it.
 */
object AttendanceCode {

    const val VERSION: String = "uf1"
    const val INTERVAL_SECONDS: Long = 30

    private const val MAC_BYTES = 10
    private const val HMAC_ALGORITHM = "HmacSHA256"

    fun counterFor(epochSeconds: Long): Long = epochSeconds / INTERVAL_SECONDS

    /** Seconds until the current code is replaced — what the countdown shows. */
    fun secondsUntilNextCode(epochSeconds: Long): Long =
        INTERVAL_SECONDS - (epochSeconds % INTERVAL_SECONDS)

    fun build(seed: String, memberRef: String, tenantId: String, counter: Long): String =
        "$VERSION.$memberRef.$counter.${mac(seed, memberRef, tenantId, counter)}"

    private fun mac(seed: String, memberRef: String, tenantId: String, counter: Long): String {
        val hmac = Mac.getInstance(HMAC_ALGORITHM).apply {
            init(SecretKeySpec(seed.toByteArray(Charsets.UTF_8), HMAC_ALGORITHM))
        }
        val digest = hmac.doFinal("$tenantId|$memberRef|$counter".toByteArray(Charsets.UTF_8))
        return base32(digest.copyOf(MAC_BYTES))
    }

    /**
     * RFC 4648 Base32, upper case, no padding.
     *
     * Hand-rolled because `java.util.Base64` is Base*64* and Android ships no
     * Base32. Ten bytes divide into exactly sixteen characters, so the partial
     * final group that makes Base32 fiddly never arises — but the loop handles
     * it anyway rather than encoding an assumption the caller could break.
     */
    private fun base32(bytes: ByteArray): String {
        val alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
        val out = StringBuilder()
        var buffer = 0L
        var bitsLeft = 0

        for (byte in bytes) {
            buffer = (buffer shl 8) or (byte.toLong() and 0xFF)
            bitsLeft += 8
            while (bitsLeft >= 5) {
                out.append(alphabet[((buffer shr (bitsLeft - 5)) and 0x1F).toInt()])
                bitsLeft -= 5
            }
        }
        if (bitsLeft > 0) {
            out.append(alphabet[((buffer shl (5 - bitsLeft)) and 0x1F).toInt()])
        }
        return out.toString()
    }
}
