plugins {
    id("unefy.android.library")
    id("unefy.android.hilt")
    alias(libs.plugins.kotlin.serialization)
}

android {
    namespace = "com.unefy.core.auth"
}

dependencies {
    api(project(":core:model"))
    api(project(":core:network"))

    implementation(libs.androidx.datastore.preferences)
    implementation(libs.ktor.client.core)
    implementation(libs.ktor.client.okhttp)
    // The bearer provider caches its token; clearing it on sign-out is what
    // stops requests going out as the previous account.
    implementation(libs.ktor.client.auth)
    implementation(libs.ktor.client.content.negotiation)
    implementation(libs.ktor.serialization.kotlinx.json)
    implementation(libs.kotlinx.serialization.json)
    implementation(libs.kotlinx.coroutines.android)

    // Google sign-in reads the accounts already on the device through
    // Credential Manager — no browser, no redirect, no Custom Tab.
    implementation(libs.androidx.credentials)
    implementation(libs.androidx.credentials.play.services.auth)
    implementation(libs.googleid)

    implementation(libs.hilt.android)
    ksp(libs.hilt.compiler)

    testImplementation(libs.junit)
    testImplementation(libs.kotlinx.coroutines.test)
    // The Google calls are tested against a stubbed engine, so the DTOs are
    // really decoded rather than mocked away.
    testImplementation(libs.ktor.client.mock)
    testImplementation(kotlin("test"))
}
