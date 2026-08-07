plugins {
    id("unefy.android.library")
    id("unefy.android.compose")
    id("unefy.android.hilt")
    alias(libs.plugins.kotlin.serialization)
}

android {
    namespace = "com.unefy.feature.scoring"
}

dependencies {
    implementation(project(":core:model"))
    implementation(project(":core:network"))
    implementation(project(":core:designsystem"))
    // The offline write queue and the member's own history live in Room; the
    // member picker reads the synced member mirror that core:sync fills.
    implementation(project(":core:database"))
    implementation(project(":core:sync"))

    val composeBom = platform(libs.androidx.compose.bom)
    implementation(composeBom)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.hilt.navigation.compose)
    implementation(libs.androidx.core.ktx)

    // Draining the queue when the network returns, not when a screen happens
    // to be open — the same shape as the check-in queue in feature:attendance.
    implementation(libs.androidx.work.runtime)
    implementation(libs.androidx.hilt.work)
    ksp(libs.androidx.hilt.compiler)

    // Photographing the target. Compose-native viewfinder, no AndroidView.
    implementation(libs.androidx.camera.core)
    implementation(libs.androidx.camera.camera2)
    implementation(libs.androidx.camera.lifecycle)
    implementation(libs.androidx.camera.compose)

    implementation(libs.kotlinx.serialization.json)
    implementation(libs.hilt.android)
    ksp(libs.hilt.compiler)

    testImplementation(libs.junit)
    testImplementation(project(":core:testing"))
    testImplementation(libs.kotlinx.coroutines.test)
}
