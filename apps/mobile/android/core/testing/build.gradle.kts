plugins {
    id("unefy.android.library")
}

android {
    namespace = "com.unefy.core.testing"
}

dependencies {
    // api, not implementation: a test that takes a FakeCoordinator sees the
    // SyncCoordinator types through this module.
    api(project(":core:sync"))
    api(libs.kotlinx.coroutines.android)
}
