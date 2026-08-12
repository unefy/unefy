plugins {
    id("unefy.android.library")
    id("unefy.android.compose")
    id("unefy.android.hilt")
    alias(libs.plugins.kotlin.serialization)
}

android {
    namespace = "com.unefy.feature.documents"
}

dependencies {
    implementation(project(":core:model"))
    implementation(project(":core:network"))
    implementation(project(":core:designsystem"))
    // The members mirror, for two things this module cannot ask the API for
    // without a round trip per row: the name beside a document, and the list to
    // pick from when issuing one.
    implementation(project(":core:database"))

    val composeBom = platform(libs.androidx.compose.bom)
    implementation(composeBom)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.hilt.navigation.compose)

    // FileProvider, for handing a rendered document to another app.
    implementation(libs.androidx.core.ktx)

    implementation(libs.kotlinx.serialization.json)
    implementation(libs.hilt.android)
    ksp(libs.hilt.compiler)

    testImplementation(libs.junit)
    testImplementation(project(":core:testing"))
    testImplementation(libs.kotlinx.coroutines.test)
}
