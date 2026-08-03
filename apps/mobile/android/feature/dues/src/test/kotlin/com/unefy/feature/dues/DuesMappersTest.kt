package com.unefy.feature.dues

import com.unefy.core.database.DueWithMemberName
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * The same due travels two roads: DTO → mirror row → join projection → domain,
 * and DTO → domain directly (the `/dues/me` path). Named arguments mean a
 * forgotten field still compiles; distinct values make the equality catch it.
 */
class DuesMappersTest {

    @Test
    fun `the mirror path and the network path agree on every field`() {
        val dto = DuesDto(
            id = "d-1",
            memberId = "m-9",
            memberName = "Anna Bauer",
            feeName = "Erwachsene",
            amount = "120.50",
            dueDate = "2026-01-31",
            status = "open",
            paidAt = "2026-02-02T09:00:00Z",
        )

        val row = dto.toRow(generation = 7L)
        val viaMirror = DueWithMemberName(
            id = row.id,
            memberId = row.memberId,
            feeName = row.feeName,
            amount = row.amount,
            dueDate = row.dueDate,
            status = row.status,
            paidAt = row.paidAt,
            // What the join supplies at read time.
            memberName = dto.memberName.orEmpty(),
        ).toDomain()

        assertEquals(dto.toDomain(), viaMirror)
    }

    /**
     * The regression test for the drain that never happened. The sync payload
     * serialises the bare row, and its `member_name` is an explicit `null` —
     * not absent. A non-nullable DTO field with a default only covers absence;
     * the explicit null threw mid-`apply`, rolled back the transaction, and
     * took the whole sync loop down with it: the dues mirror stayed empty while
     * every other collection filled. Found on the device, not by review.
     */
    @Test
    fun `a sync payload with an explicit null member name decodes`() {
        val json = Json {
            ignoreUnknownKeys = true
            explicitNulls = false
            isLenient = true
        }
        val element = json.parseToJsonElement(
            """
            {"id":"d-1","member_id":"m-1","member_name":null,"fee_type_id":"f-1",
             "fee_name":"Erwachsene","amount":"120.50","period_start":"2026-01-01",
             "period_end":"2026-12-31","due_date":"2026-01-31","status":"open",
             "created_at":"2026-01-01T00:00:00Z","updated_at":"2026-01-01T00:00:00Z"}
            """,
        )

        val dto = json.decodeFromJsonElement(DuesDto.serializer(), element)

        assertEquals("d-1", dto.id)
        assertEquals("", dto.memberName.orEmpty())
    }
}
