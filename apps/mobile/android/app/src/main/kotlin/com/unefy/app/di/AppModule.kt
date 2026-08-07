package com.unefy.app.di

import com.unefy.app.BuildConfig
import com.unefy.core.auth.GoogleAuthConfig
import com.unefy.core.network.ApiConfig
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

/**
 * The only place the backend URL enters the graph. `core:network` stays
 * environment-agnostic; the value comes from [ServerUrlStore], which answers
 * with whatever the person chose on the login screen and otherwise with
 * BuildConfig — fed by the `unefy.apiBaseUrl` Gradle property.
 */
@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    @Provides
    @Singleton
    fun provideApiConfig(servers: ServerUrlStore): ApiConfig = ApiConfig(servers::current)

    /**
     * The Google OAuth *web* client id, from the `unefy.googleServerClientId`
     * Gradle property. Unlike the backend URL this one is fixed per build:
     * Google ties it to the package name and signing certificate, so it cannot
     * follow the server the user picks. A build without it hides the button.
     */
    @Provides
    @Singleton
    fun provideGoogleAuthConfig(): GoogleAuthConfig =
        GoogleAuthConfig(BuildConfig.GOOGLE_SERVER_CLIENT_ID)
}
