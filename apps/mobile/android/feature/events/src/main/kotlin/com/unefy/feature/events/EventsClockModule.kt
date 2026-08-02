package com.unefy.feature.events

import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import java.time.Instant
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object EventsClockModule {
    @Provides
    @Singleton
    fun provideEventsClock(): EventsClock = EventsClock { Instant.now().toString() }
}
