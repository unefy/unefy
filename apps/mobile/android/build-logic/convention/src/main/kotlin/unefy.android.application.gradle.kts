// AGP 9 ships built-in Kotlin support — applying org.jetbrains.kotlin.android
// on top of it is an error. See https://kotl.in/gradle/agp-built-in-kotlin
plugins {
    id("com.android.application")
}

android {
    compileSdk = UnefySdk.COMPILE

    defaultConfig {
        minSdk = UnefySdk.MIN
        targetSdk = UnefySdk.TARGET
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

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

kotlin {
    jvmToolchain(21)
}
