package com.unefy.feature.dues

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.unefy.core.model.DuesEntry
import com.unefy.core.model.DuesStatus
import com.unefy.core.model.DuesSummary
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

sealed interface DuesUiState {
    data object Loading : DuesUiState

    data class Content(
        val summary: DuesSummary?,
        val entries: List<DuesEntry>,
        val filter: DuesFilter,
    ) : DuesUiState {
        val visible: List<DuesEntry>
            get() = when (filter) {
                DuesFilter.ALL -> entries
                DuesFilter.OPEN -> entries.filter { it.status != DuesStatus.PAID }
                DuesFilter.PAID -> entries.filter { it.status == DuesStatus.PAID }
            }
    }

    data class Failure(val error: ApiError) : DuesUiState
}

enum class DuesFilter { ALL, OPEN, PAID }

@HiltViewModel
class DuesViewModel @Inject constructor(
    private val repository: DuesRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow<DuesUiState>(DuesUiState.Loading)
    val uiState: StateFlow<DuesUiState> = _uiState.asStateFlow()

    private var filter = DuesFilter.ALL

    init {
        load()
    }

    fun retry() = load()

    fun onFilterChange(value: DuesFilter) {
        filter = value
        // Filtering is local: the list is already in memory, so a round trip
        // would only add latency.
        _uiState.value = (_uiState.value as? DuesUiState.Content)?.copy(filter = value)
            ?: _uiState.value
    }

    private fun load() {
        _uiState.value = DuesUiState.Loading
        viewModelScope.launch {
            // Both calls in flight at once — the summary is not derived from the
            // page of entries, so waiting for one before the other is wasted time.
            val entriesDeferred = async { repository.list() }
            val summaryDeferred = async { repository.summary() }

            _uiState.value = when (val entries = entriesDeferred.await()) {
                is ApiResult.Success -> DuesUiState.Content(
                    summary = (summaryDeferred.await() as? ApiResult.Success)?.data,
                    entries = entries.data,
                    filter = filter,
                )

                is ApiResult.Failure -> DuesUiState.Failure(entries.error)
            }
        }
    }
}
