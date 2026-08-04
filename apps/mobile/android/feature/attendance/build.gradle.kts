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
    // Not for a mirror — attendance has none. The check-in confirmation listens to
    // the change stream the coordinator already holds open, so the member's phone
    // hears about a check-in made on somebody else's device.
    implementation(project(":core:sync"))

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

    // Draining the queue must outlive the app: WorkManager keeps the job across
    // process death and starts it when the network constraint is met.
    implementation(libs.androidx.work.runtime)
    implementation(libs.androidx.hilt.work)
    ksp(libs.androidx.hilt.compiler)

    implementation(libs.kotlinx.serialization.json)
    implementation(libs.hilt.android)
    ksp(libs.hilt.compiler)

    testImplementation(libs.junit)
    // FakeCoordinator, so the doorbell can be rung without a socket.
    testImplementation(project(":core:testing"))
    testImplementation(libs.kotlinx.coroutines.test)
    // The pick-list test runs the real ApiClient against a mock engine, so the
    // "no network once mirrored" claim counts actual requests.
    testImplementation(libs.ktor.client.mock)
    testImplementation(libs.ktor.client.content.negotiation)
    testImplementation(libs.ktor.serialization.kotlinx.json)
}
