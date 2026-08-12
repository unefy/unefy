plugins {
    id("unefy.android.library")
    id("unefy.android.compose")
}

android {
    namespace = "com.unefy.core.designsystem"
}

dependencies {
    // The scoring engine and target geometry: the canvas draws rings and scores
    // taps with the same code the rest of the app uses. core:model is pure
    // Kotlin, so this respects the module rules.
    api(project(":core:model"))

    val composeBom = platform(libs.androidx.compose.bom)
    implementation(composeBom)

    // api, not implementation: every feature module consumes Compose and
    // Material 3 through the design system rather than declaring them itself.
    api(libs.androidx.compose.material3)
    api(libs.androidx.compose.animation)
    api(libs.androidx.compose.ui)
    api(libs.androidx.compose.ui.graphics)
    api(libs.androidx.compose.ui.tooling.preview)

    // Backdrop blur: Compose can blur a layer's own content but not what is
    // behind it, which is exactly what a glass surface needs.
    implementation(libs.haze)
    implementation(libs.haze.materials)

    debugImplementation(libs.androidx.compose.ui.tooling)

    testImplementation(libs.junit)
}
