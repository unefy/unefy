package com.unefy.app

import android.app.Application
import android.content.Context
import androidx.test.runner.AndroidJUnitRunner
import dagger.hilt.android.testing.HiltTestApplication

/**
 * Swaps [UnefyApplication] for Hilt's test application so instrumented tests can
 * replace modules with `@TestInstallIn`. Referenced by `testInstrumentationRunner`
 * in the app's build script.
 */
class UnefyTestRunner : AndroidJUnitRunner() {
    override fun newApplication(
        classLoader: ClassLoader?,
        className: String?,
        context: Context?,
    ): Application = super.newApplication(classLoader, HiltTestApplication::class.java.name, context)
}
