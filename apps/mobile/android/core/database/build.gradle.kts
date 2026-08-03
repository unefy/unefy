plugins {
    id("unefy.android.library")
    id("unefy.android.hilt")
}

android {
    namespace = "com.unefy.core.database"

    defaultConfig {
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    // Room writes the schema JSON here. Checked in on purpose: a migration is
    // reviewed against the previous schema, and without the file there is
    // nothing to review against.
    ksp { arg("room.schemaLocation", "$projectDir/schemas") }

    // The same directory as instrumented-test assets, which is what
    // MigrationTestHelper reads to build a database at an older version.
    sourceSets {
        getByName("androidTest").assets.srcDir(files("$projectDir/schemas"))
    }
}

dependencies {
    implementation(libs.androidx.room.runtime)
    implementation(libs.androidx.room.ktx)
    ksp(libs.androidx.room.compiler)

    implementation(libs.hilt.android)
    ksp(libs.hilt.compiler)

    testImplementation(libs.junit)
    testImplementation(libs.kotlinx.coroutines.test)

    // Room and SQLite are the things under test here, so these run on a device
    // rather than under a JVM fake. Real migrations, real collation, real
    // transactions.
    androidTestImplementation(libs.junit)
    androidTestImplementation(libs.androidx.room.testing)
    androidTestImplementation(libs.androidx.test.core)
    androidTestImplementation(libs.androidx.test.ext.junit)
    androidTestImplementation(libs.androidx.test.runner)
    androidTestImplementation(libs.kotlinx.coroutines.test)
}
