plugins {
    id("unefy.android.library")
    id("unefy.android.compose")
    id("unefy.android.hilt")
    alias(libs.plugins.kotlin.serialization)
}

android {
    namespace = "com.unefy.feature.events"
}

dependencies {
    implementation(project(":core:model"))
    implementation(project(":core:network"))
    implementation(project(":core:designsystem"))
    // Room mirrors the event list, and core:sync fills it.
    implementation(project(":core:database"))
    implementation(project(":core:sync"))
    // The background-drain observer that renders "Neuer Termin" locally.
    implementation(project(":core:push"))

    val composeBom = platform(libs.androidx.compose.bom)
    implementation(composeBom)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.hilt.navigation.compose)
    implementation(libs.androidx.core.ktx)

    implementation(libs.kotlinx.serialization.json)
    implementation(libs.hilt.android)
    ksp(libs.hilt.compiler)

    testImplementation(libs.junit)
    testImplementation(project(":core:testing"))
    testImplementation(libs.kotlinx.coroutines.test)
}
