plugins {
    id("unefy.android.library")
    id("unefy.android.compose")
    id("unefy.android.hilt")
    alias(libs.plugins.kotlin.serialization)
}

android {
    namespace = "com.unefy.feature.attendance"
}

dependencies {
    implementation(project(":core:model"))
    implementation(project(":core:network"))
    implementation(project(":core:designsystem"))
    // For TokenCrypto: the seed is a credential and must not sit in DataStore
    // in the clear.
    implementation(project(":core:auth"))
    // The offline check-in queue: a check-in taken without a connection exists
    // nowhere else until it syncs.
    implementation(project(":core:database"))

    val composeBom = platform(libs.androidx.compose.bom)
    implementation(composeBom)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.hilt.navigation.compose)

    implementation(libs.androidx.datastore.preferences)

    // Encoding only. The scanner reads codes with ML Kit, which is a different
    // problem and a different library.
    implementation(libs.zxing.core)

    implementation(libs.androidx.camera.core)
    implementation(libs.androidx.camera.camera2)
    implementation(libs.androidx.camera.lifecycle)
    implementation(libs.androidx.camera.compose)
    implementation(libs.mlkit.barcode.scanning)

    implementation(libs.kotlinx.serialization.json)
    implementation(libs.hilt.android)
    ksp(libs.hilt.compiler)

    testImplementation(libs.junit)
    testImplementation(libs.kotlinx.coroutines.test)
}
