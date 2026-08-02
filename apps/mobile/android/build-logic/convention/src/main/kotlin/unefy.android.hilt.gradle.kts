// Applied on top of unefy.android.library or unefy.android.application. Modules
// declare the Hilt artifacts themselves; this only wires the plugins so the
// version lives in exactly one place.
plugins {
    id("com.google.devtools.ksp")
    id("com.google.dagger.hilt.android")
}
