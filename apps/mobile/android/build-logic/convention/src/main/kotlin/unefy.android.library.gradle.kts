// AGP 9 ships built-in Kotlin support — applying org.jetbrains.kotlin.android
// on top of it is an error. See https://kotl.in/gradle/agp-built-in-kotlin
plugins {
    id("com.android.library")
}

android {
    compileSdk = UnefySdk.COMPILE

    defaultConfig {
        minSdk = UnefySdk.MIN
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_21
        targetCompatibility = JavaVersion.VERSION_21
    }

    buildFeatures {
        buildConfig = false
        aidl = false
        shaders = false
    }
}

kotlin {
    jvmToolchain(21)
}
