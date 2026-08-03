package com.unefy.core.testing

import java.io.File
import kotlinx.serialization.ExperimentalSerializationApi
import kotlinx.serialization.descriptors.SerialDescriptor
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.boolean
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

/**
 * The drift guard between hand-written DTOs and the backend's response models.
 *
 * `docs/api/mobile-contract.json` is exported from the Pydantic schemas
 * (backend/scripts/export_mobile_contract.py) and pinned fresh by a backend
 * test; this side asserts each DTO against it. Two failure classes, both of
 * which otherwise surface only at runtime on a phone:
 *
 * - **A field the backend no longer sends.** kotlinx quietly decodes it to its
 *   default, and the screen shows an empty value with nothing to grep for.
 * - **A nullable server field behind a non-nullable DTO field.** A default
 *   only covers *absence*; an explicit `null` throws mid-decode. The dues
 *   mirror once stayed empty for exactly this, and the failure took the whole
 *   sync loop with it.
 */
@OptIn(ExperimentalSerializationApi::class)
object MobileContract {

    private val contract by lazy {
        var dir: File? = File(System.getProperty("user.dir"))
        while (dir != null && !File(dir, "docs/api/mobile-contract.json").isFile) {
            dir = dir.parentFile
        }
        val file = requireNotNull(dir?.let { File(it, "docs/api/mobile-contract.json") }) {
            "docs/api/mobile-contract.json not found above ${System.getProperty("user.dir")}"
        }
        Json.parseToJsonElement(file.readText()).jsonObject
    }

    /**
     * Asserts every serial name of [descriptor] against [schema]'s fields.
     *
     * @param tolerateNonNullable serial names where the contract says nullable
     *   but the DTO deliberately stays non-nullable — each entry is a claim
     *   that the backend never actually sends null there, and it should carry
     *   a comment at the call site saying why.
     */
    fun assertMirrors(
        descriptor: SerialDescriptor,
        schema: String,
        tolerateNonNullable: Set<String> = emptySet(),
    ) {
        val entry = requireNotNull(contract[schema]) {
            "Schema '$schema' is not in the mobile contract - add it to " +
                "backend/scripts/export_mobile_contract.py"
        }
        val fields = entry.jsonObject.getValue("fields").jsonObject

        for (i in 0 until descriptor.elementsCount) {
            val name = descriptor.getElementName(i)
            val spec = fields[name]
            check(spec != null) {
                "${descriptor.serialName}.$name: '$schema' no longer carries '$name' - " +
                    "the backend renamed or removed it, and this DTO would quietly " +
                    "decode its default forever"
            }

            val serverNullable = spec.jsonObject.getValue("nullable").jsonPrimitive.boolean
            val dtoNullable = descriptor.getElementDescriptor(i).isNullable
            check(!serverNullable || dtoNullable || name in tolerateNonNullable) {
                "${descriptor.serialName}.$name: the server may send an explicit null " +
                    "but the DTO field is non-nullable - a default only covers absence, " +
                    "an explicit null throws mid-decode (the dues mirror stayed empty " +
                    "for exactly this once)"
            }
        }
    }
}
