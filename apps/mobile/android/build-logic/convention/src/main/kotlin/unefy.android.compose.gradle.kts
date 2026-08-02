import com.android.build.api.dsl.CommonExtension

plugins {
    id("org.jetbrains.kotlin.plugin.compose")
}

// Applied on top of unefy.android.library or unefy.android.application, which
// own the android { } block. Only the Compose build feature is toggled here, so
// modules without UI (core:network, core:model) never pay for the Compose
// compiler. CommonExtension lost its type parameters in AGP 9, hence the cast
// rather than a typed extensions.configure call.
val androidExtension = extensions.getByName("android") as CommonExtension
androidExtension.buildFeatures.compose = true
