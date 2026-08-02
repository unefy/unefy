plugins {
    id("unefy.android.library")
    id("unefy.android.hilt")
}

android {
    namespace = "com.unefy.core.database"

    // Room writes the schema JSON here. Checked in on purpose: a migration is
    // reviewed against the previous schema, and without the file there is
    // nothing to review against. A MigrationTestHelper will need this directory
    // wired up as androidTest assets — not yet, there is one version.
    ksp { arg("room.schemaLocation", "$projectDir/schemas") }
}

dependencies {
    implementation(libs.androidx.room.runtime)
    implementation(libs.androidx.room.ktx)
    ksp(libs.androidx.room.compiler)

    implementation(libs.hilt.android)
    ksp(libs.hilt.compiler)

    testImplementation(libs.junit)
    testImplementation(libs.kotlinx.coroutines.test)
}
