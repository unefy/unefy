package com.unefy.app.di

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
}
