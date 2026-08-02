package com.unefy.feature.attendance

import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import java.time.Instant
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object AttendanceClockModule {
    @Provides
    @Singleton
    fun provideAttendanceClock(): AttendanceClock = AttendanceClock { Instant.now().epochSecond }
}
