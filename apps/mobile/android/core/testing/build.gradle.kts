plugins {
    id("unefy.android.library")
    alias(libs.plugins.kotlin.serialization)
}

android {
    namespace = "com.unefy.core.testing"
}

dependencies {
    // api, not implementation: a test that takes a FakeCoordinator sees the
    // SyncCoordinator types through this module.
    api(project(":core:sync"))
    api(libs.kotlinx.coroutines.android)
    // MobileContract reads and walks the committed contract JSON.
    implementation(libs.kotlinx.serialization.json)
}
