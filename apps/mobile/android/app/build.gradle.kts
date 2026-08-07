plugins {
    id("unefy.android.application")
    id("unefy.android.compose")
    id("unefy.android.hilt")
    alias(libs.plugins.kotlin.serialization)
}

// Conditionally, not unconditionally: the google-services plugin hard-fails
// without its json, and that file is deliberately not checked in — a fork must
// not ship somebody else's Firebase project, and a self-hoster has none. Both
// variants must build; without the file the app simply never registers for
// push (see core:push, which guards at runtime the same way).
if (file("google-services.json").exists()) {
    apply(plugin = libs.plugins.google.services.get().pluginId)
}

// No hardcoded URLs (apps/mobile/CLAUDE.md). This is the address a build ships
// with, not the only one it can reach: the login screen can point the app at
// another server, which is what a self-hosted club needs. Override in
// gradle.properties with the emulator alias (10.0.2.2) or the machine's LAN
// address while developing.
// Read from local.properties too, and that file is gitignored on purpose. The
// override used to sit in the tracked gradle.properties, where one developer's
// LAN address silently pinned every build in the repository — including one
// meant for a phone that has never seen that network.
//
// `takeIf` and not `getOrElse`: an empty property is present, so `getOrElse`
// hands back "" and the app ships with no address at all.
val localApiBaseUrl: String? = rootProject.file("local.properties")
    .takeIf { it.exists() }
    ?.readLines()
    ?.firstOrNull { it.trimStart().startsWith("unefy.apiBaseUrl=") }
    ?.substringAfter('=')
    ?.trim()

val apiBaseUrl: String = (providers.gradleProperty("unefy.apiBaseUrl").orNull ?: localApiBaseUrl)
    ?.takeIf { it.isNotBlank() }
    ?: "https://test.unefy.app"

android {
    namespace = "com.unefy.app"

    defaultConfig {
        applicationId = "com.unefy.app"
        versionCode = 1
        versionName = "0.1.0"
        buildConfigField("String", "API_BASE_URL", "\"$apiBaseUrl\"")

        // Hilt's runner swaps in HiltTestApplication, so instrumented tests can
        // replace modules with @TestInstallIn.
        testInstrumentationRunner = "com.unefy.app.UnefyTestRunner"
    }

    buildFeatures {
        buildConfig = true
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
    }
}

// connectedAndroidTest uninstalls both APKs when it finishes, which is correct
// for CI and a nuisance on a real device — the app simply vanishes after every
// run. finalizedBy puts it back, and runs even when the tests fail, which is
// exactly when someone wants to open the app and look.
tasks.matching { it.name == "connectedDebugAndroidTest" }.configureEach {
    finalizedBy("installDebug")
}

dependencies {
    implementation(project(":core:model"))
    implementation(project(":core:designsystem"))
    implementation(project(":core:network"))
    implementation(project(":core:auth"))
    // MainActivity starts the change stream and the syncs it triggers.
    implementation(project(":core:sync"))
    // MainActivity keeps the push registration in step with sign-in.
    implementation(project(":core:push"))
    implementation(project(":feature:attendance"))
    implementation(project(":feature:members"))
    implementation(project(":feature:events"))
    implementation(project(":feature:dues"))
    implementation(project(":feature:competitions"))

    val composeBom = platform(libs.androidx.compose.bom)
    implementation(composeBom)
    androidTestImplementation(composeBom)

    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)

    // Adaptive layouts are mandatory at targetSdk 36 — orientation and
    // resizability restrictions are ignored on displays >= 600dp.
    implementation(libs.androidx.adaptive)
    implementation(libs.androidx.adaptive.layout)
    implementation(libs.androidx.adaptive.navigation)
    implementation(libs.androidx.compose.material3.adaptive.navigation.suite)

    implementation(libs.androidx.navigation3.runtime)
    implementation(libs.androidx.navigation3.ui)
    implementation(libs.androidx.lifecycle.viewmodel.navigation3)

    implementation(libs.androidx.datastore.preferences)
    implementation(libs.haze)
    implementation(libs.androidx.work.runtime)
    implementation(libs.androidx.hilt.work)
    ksp(libs.androidx.hilt.compiler)
    implementation(libs.hilt.android)
    implementation(libs.androidx.hilt.navigation.compose)
    ksp(libs.hilt.compiler)

    debugImplementation(libs.androidx.compose.ui.tooling)
    debugImplementation(libs.androidx.compose.ui.test.manifest)

    testImplementation(libs.junit)
    testImplementation(libs.kotlinx.coroutines.test)
    // sealedSubclasses — how EntryProviderCoverageTest enumerates the keys.
    testImplementation(libs.kotlin.reflect)

    androidTestImplementation(libs.androidx.compose.ui.test.junit4)
    androidTestImplementation(libs.androidx.test.ext.junit)
    androidTestImplementation(libs.androidx.test.runner)
    androidTestImplementation(libs.hilt.android.testing)
    kspAndroidTest(libs.hilt.compiler)
    // The smoke test drives the real dependency graph and swaps only the Ktor
    // engine, so DTO decoding is exercised rather than mocked away.
    androidTestImplementation(libs.ktor.client.mock)
    androidTestImplementation(libs.ktor.client.core)
    androidTestImplementation(libs.ktor.client.auth)
    androidTestImplementation(libs.ktor.client.content.negotiation)
    androidTestImplementation(libs.ktor.serialization.kotlinx.json)
    androidTestImplementation(libs.kotlinx.coroutines.test)
}
