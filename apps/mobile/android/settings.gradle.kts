pluginManagement {
    includeBuild("build-logic")
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

plugins {
    id("org.gradle.toolchains.foojay-resolver-convention") version "1.0.0"
}

rootProject.name = "unefy-android"

include(":app")

include(":core:model")
include(":core:designsystem")
include(":core:network")
include(":core:auth")
include(":core:database")
include(":core:sync")
include(":core:testing")
include(":core:push")

include(":feature:attendance")
include(":feature:members")
include(":feature:events")
include(":feature:dues")
include(":feature:competitions")
include(":feature:scoring")
