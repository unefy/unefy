// For modules with no Android dependencies at all — core:model, and later the
// pure-logic parts such as the scoring engine. No version on the plugin id:
// the Kotlin plugin already comes from build-logic's own classpath.
plugins {
    id("org.jetbrains.kotlin.jvm")
}

kotlin {
    jvmToolchain(21)
}
