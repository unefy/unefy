plugins {
    id("unefy.android.library")
    id("unefy.android.hilt")
    alias(libs.plugins.kotlin.serialization)
}

android {
    namespace = "com.unefy.core.sync"
}

dependencies {
    // core:auth for SignOutTask — clearing the mirror when an account leaves is
    // this module's job, not each feature's. A feature that forgot would leak the
    // previous club's data to the next person signing in on the phone.
    implementation(project(":core:auth"))
    implementation(project(":core:database"))
    implementation(project(":core:network"))

    implementation(libs.androidx.core.ktx)
    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.kotlinx.serialization.json)
    // The SSE plugin ships inside ktor-client-core (io.ktor.client.plugins.sse) —
    // there is no separate ktor-client-sse artifact at this version. Ktor's own
    // plugin rather than OkHttp's EventSource, because it runs through the same
    // pipeline as every other call: the Auth plugin attaches the bearer token and
    // refreshes it on 401 with no extra code.
    implementation(libs.ktor.client.core)

    implementation(libs.hilt.android)
    ksp(libs.hilt.compiler)

    testImplementation(libs.junit)
    testImplementation(libs.kotlinx.coroutines.test)
    testImplementation(libs.ktor.client.mock)
    testImplementation(libs.ktor.client.content.negotiation)
    testImplementation(libs.ktor.serialization.kotlinx.json)
}
