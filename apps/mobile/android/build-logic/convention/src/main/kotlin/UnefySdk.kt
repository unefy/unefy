/**
 * Single source of truth for SDK levels across every module.
 *
 * compileSdk is 37 because the AndroidX libraries the app depends on
 * (hilt-navigation-compose 1.4.0, lifecycle 2.11.0, navigation3) declare it as
 * their minimum via AAR metadata — building against 36 fails the dependency
 * check. targetSdk deliberately stays at 36: compiling against the newest SDK
 * is free, opting into a new SDK's runtime behaviour changes is not.
 */
object UnefySdk {
    const val COMPILE = 37
    const val TARGET = 36
    const val MIN = 31
}
