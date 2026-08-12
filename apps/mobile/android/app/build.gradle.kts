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

// The one address every build ships with. Not overridable from the build on
// purpose: an override in local.properties is invisible in the APK, and a
// developer machine's LAN address ended up in builds meant for phones that
// had never seen that network — including the ones handed to other people.
//
// A different server — a local backend, a club's own instance — is chosen in
// the app itself, at the foot of the login screen. That path is the one real
// users have, so it is the one that gets tested.
//
// The API host, not the web app: "/api/v1/..." is appended to this, so a
// frontend hostname answers every request with HTML and nobody can sign in.
val apiBaseUrl = "https://api.unefy.app"

// Still read from local.properties, but only for the Google client id below:
// that one is per-project rather than per-build, must not be checked in, and
// has no in-app equivalent. `takeIf` and not `getOrElse`, because an empty
// property is present and would hand back "" instead of falling through.
fun buildProperty(name: String): String? = (
    providers.gradleProperty(name).orNull
        ?: rootProject.file("local.properties")
            .takeIf { it.exists() }
            ?.readLines()
            ?.firstOrNull { it.trimStart().startsWith("$name=") }
            ?.substringAfter('=')
    )?.trim()?.takeIf { it.isNotBlank() }

// The Google OAuth *web* client id — Google's `serverClientId`, the one that
// lands in the ID token's `aud` claim. Empty by default and empty in a fork:
// a client id is bound to a package name and signing certificate in somebody's
// Google Cloud project, so it cannot be checked in usefully. Without it the
// login screen simply has no Google button.
val googleServerClientId: String = buildProperty("unefy.googleServerClientId").orEmpty()

// Release signing, same shape as the Google client id: from local.properties,
// absent in a fork. The keystore itself lives outside the repository — a
// signing key that anyone can pull is not a signing key.
//
// Conditional, like the google-services plugin above: without the keystore the
// release build still assembles, it just comes out unsigned. That keeps
// `assembleRelease` usable in CI and in a fork, where nobody has this key.
// An unsigned APK will not install on a device — that is the point, it says
// "you are not the one who publishes this app" rather than silently shipping
// something signed with a stand-in key.
val releaseKeystore = buildProperty("unefy.releaseKeystore")?.let(::file)?.takeIf { it.exists() }

android {
    namespace = "com.unefy.app"

    if (releaseKeystore != null) {
        signingConfigs {
            create("release") {
                storeFile = releaseKeystore
                storePassword = buildProperty("unefy.releaseKeystorePassword")
                keyAlias = buildProperty("unefy.releaseKeyAlias")
                keyPassword = buildProperty("unefy.releaseKeyPassword")
            }
        }
    }

    defaultConfig {
        applicationId = "com.unefy.app"
        // Bumped per build handed out: Firebase App Distribution and the
        // devices both key updates off this, so two builds sharing a code look
        // like the same build and testers never see the second one.
        versionCode = 2
        versionName = "0.1.1"
        buildConfigField("String", "API_BASE_URL", "\"$apiBaseUrl\"")
        buildConfigField("String", "GOOGLE_SERVER_CLIENT_ID", "\"$googleServerClientId\"")

        // Hilt's runner swaps in HiltTestApplication, so instrumented tests can
        // replace modules with @TestInstallIn.
        testInstrumentationRunner = "com.unefy.app.UnefyTestRunner"
    }

    buildFeatures {
        buildConfig = true
    }

    buildTypes {
        release {
            if (releaseKeystore != null) {
                signingConfig = signingConfigs.getByName("release")
            }
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
    implementation(project(":feature:documents"))
    implementation(project(":feature:competitions"))
    implementation(project(":feature:scoring"))

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
