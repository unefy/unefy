package com.unefy.app

import androidx.activity.ComponentActivity
import dagger.hilt.android.AndroidEntryPoint

/**
 * An empty host for composables under test.
 *
 * [MainActivity] would work too, but it starts at [UnefyRoot] and therefore at
 * the session check — a navigation test would have to fake a signed-in account
 * before it could reach the first screen. Hosting [MainNavigation] directly keeps
 * the test about navigation.
 *
 * In the debug variant rather than in `androidTest`: an activity declared by the
 * test APK belongs to the `com.unefy.app.test` process, and Instrumentation
 * running as `com.unefy.app` cannot start it. Debug builds carry it, release
 * builds do not.
 */
@AndroidEntryPoint
class HiltTestActivity : ComponentActivity()
