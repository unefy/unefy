package com.unefy.feature.members

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.unefy.core.model.Member
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * UI state as a sealed hierarchy — loading, content and failure are distinct
 * states rather than a bag of nullable fields, so a screen cannot render an
 * impossible combination.
 */
sealed interface MembersUiState {
    data object Loading : MembersUiState

    data class Content(
        val members: List<Member>,
        val query: String = "",
        val isRefreshing: Boolean = false,
    ) : MembersUiState

    data class Failure(val error: ApiError) : MembersUiState
}

@HiltViewModel
class MembersViewModel @Inject constructor(
    private val repository: MembersRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow<MembersUiState>(MembersUiState.Loading)
    val uiState: StateFlow<MembersUiState> = _uiState.asStateFlow()

    private var query: String = ""
    private var inFlight: Job? = null

    init {
        load()
    }

    fun onQueryChange(value: String) {
        query = value
        _uiState.update { current ->
            if (current is MembersUiState.Content) current.copy(query = value) else current
        }
        load(showSpinner = false)
    }

    fun refresh() = load(showSpinner = false, refreshing = true)

    fun retry() = load()

    private fun load(showSpinner: Boolean = true, refreshing: Boolean = false) {
        // A new search supersedes the previous one; without this, a slow earlier
        // response could land after a faster later one and show stale results.
        inFlight?.cancel()

        if (showSpinner) _uiState.value = MembersUiState.Loading
        if (refreshing) {
            _uiState.update { c ->
                if (c is MembersUiState.Content) c.copy(isRefreshing = true) else c
            }
        }

        inFlight = viewModelScope.launch {
            when (val result = repository.list(search = query)) {
                is ApiResult.Success -> _uiState.value = MembersUiState.Content(
                    members = result.data,
                    query = query,
                )

                is ApiResult.Failure -> _uiState.value = MembersUiState.Failure(result.error)
            }
        }
    }
}
