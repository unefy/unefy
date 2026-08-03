package com.unefy.core.push

import com.unefy.core.auth.SignOutTask
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import dagger.multibindings.IntoSet
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Sign-out for push: the server forgets this device, the device forgets its
 * token.
 *
 * Without this the old club keeps waking a phone that now belongs to somebody
 * else's account — the same leftover class as the check-in seed, and the same
 * fix: a [SignOutTask] the auth layer runs without knowing this module exists.
 * It runs while the session is still valid (see `AuthRepository.signOut`), so
 * the unregister call can authenticate.
 */
@Singleton
class PushSignOut @Inject constructor(
    private val registrar: PushRegistrar,
) : SignOutTask {

    override suspend fun onSignOut() {
        registrar.unregister()
    }
}

@Module
@InstallIn(SingletonComponent::class)
abstract class PushSignOutModule {
    @Binds
    @IntoSet
    abstract fun bindPushSignOut(impl: PushSignOut): SignOutTask
}
