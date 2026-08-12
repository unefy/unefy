package com.unefy.feature.documents

import com.unefy.core.testing.MobileContract
import org.junit.Test

/** The hand-written DTOs against the committed backend contract. */
class DocumentDtoDriftTest {

    @Test
    fun `IssuedDocumentDto mirrors IssuedDocumentResponse`() {
        MobileContract.assertMirrors(
            IssuedDocumentDto.serializer().descriptor,
            "IssuedDocumentResponse",
        )
    }

    @Test
    fun `TemplateDto mirrors TemplateResponse`() {
        MobileContract.assertMirrors(TemplateDto.serializer().descriptor, "TemplateResponse")
    }
}
