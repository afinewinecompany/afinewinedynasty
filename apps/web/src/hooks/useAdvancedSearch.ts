'use client';

import { useState, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api/client';

/**
 * Advanced search criteria interface matching backend API
 */
export interface AdvancedSearchCriteria {
  // Statistical criteria
  min_batting_avg?: number;
  max_batting_avg?: number;
  min_on_base_pct?: number;
  max_on_base_pct?: number;
  min_slugging_pct?: number;
  max_slugging_pct?: number;
  min_era?: number;
  max_era?: number;
  min_whip?: number;
  max_whip?: number;
  min_woba?: number;
  max_woba?: number;
  min_wrc_plus?: number;
  max_wrc_plus?: number;

  // Basic prospect criteria
  positions?: string[];
  organizations?: string[];
  levels?: string[];
  min_age?: number;
  max_age?: number;
  min_eta_year?: number;
  max_eta_year?: number;

  // Scouting criteria
  min_overall_grade?: number;
  max_overall_grade?: number;
  scouting_sources?: string[];
  min_hit_grade?: number;
  max_hit_grade?: number;
  min_power_grade?: number;
  max_power_grade?: number;
  min_future_value?: number;
  max_future_value?: number;
  risk_levels?: string[];

  // ML criteria
  min_success_probability?: number;
  max_success_probability?: number;
  min_confidence_score?: number;
  max_confidence_score?: number;
  prediction_types?: string[];

  // Performance criteria
  improvement_lookback_days?: number;
  min_improvement_rate?: number;

  // Search text
  search_query?: string;

  // Pagination and sorting
  page?: number;
  size?: number;
  sort_by?: string;
}

/**
 * Search results interface
 */
export interface SearchResults {
  prospects: any[];
  total_count: number;
  page: number;
  size: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
  search_metadata: {
    applied_filters: {
      statistical: boolean;
      scouting: boolean;
      ml_predictions: boolean;
      basic_filters: boolean;
      text_search: boolean;
    };
    sort_by: string;
    search_complexity: number;
  };
}

/**
 * Hook for managing advanced search state and operations
 *
 * Provides comprehensive search functionality with criteria management,
 * search execution, and result handling.
 *
 * @returns Advanced search state and operations
 */
export function useAdvancedSearch() {
  const [searchCriteria, setSearchCriteria] = useState<AdvancedSearchCriteria>({
    page: 1,
    size: 25,
    sort_by: 'relevance',
  });
  const [hasSearched, setHasSearched] = useState(false);
  const queryClient = useQueryClient();

  // Search execution mutation
  const searchMutation = useMutation({
    mutationFn: async (criteria: AdvancedSearchCriteria) => {
      const response = await api.post('/search/advanced', criteria);
      return response.data as SearchResults;
    },
    onSuccess: () => {
      setHasSearched(true);
      // Invalidate related queries
      queryClient.invalidateQueries({ queryKey: ['search-history'] });
    },
  });

  // Get search criteria options
  const { data: searchOptions } = useQuery({
    queryKey: ['search-criteria-options'],
    queryFn: async () => {
      const response = await api.get('/search/criteria/options');
      return response.data;
    },
  });

  /**
   * Update search criteria
   */
  const updateCriteria = useCallback(
    (updates: Partial<AdvancedSearchCriteria>) => {
      setSearchCriteria((prev) => ({
        ...prev,
        ...updates,
        // Reset page when criteria change (unless page is being explicitly set)
        page: 'page' in updates ? updates.page : 1,
      }));
    },
    []
  );

  /**
   * Execute search with current criteria
   */
  const executeSearch = useCallback(() => {
    searchMutation.mutate(searchCriteria);
  }, [searchCriteria, searchMutation]);

  /**
   * Reset search criteria to defaults
   */
  const resetCriteria = useCallback(() => {
    setSearchCriteria({
      page: 1,
      size: 25,
      sort_by: 'relevance',
    });
    setHasSearched(false);
  }, []);

  /**
   * Load saved search criteria
   */
  const loadSavedSearch = useCallback((savedSearchCriteria: any) => {
    setSearchCriteria({
      ...savedSearchCriteria,
      page: 1,
      size: 25,
      sort_by: savedSearchCriteria.sort_by || 'relevance',
    });
  }, []);

  /**
   * Update pagination
   */
  const updatePagination = useCallback(
    (page: number, size?: number) => {
      updateCriteria({
        page,
        ...(size && { size }),
      });
      // Auto-execute search with new pagination
      searchMutation.mutate({
        ...searchCriteria,
        page,
        ...(size && { size }),
      });
    },
    [searchCriteria, searchMutation, updateCriteria]
  );

  /**
   * Check if criteria has meaningful filters
   */
  const hasActiveFilters = useCallback(() => {
    const { page, size, sort_by, ...filters } = searchCriteria;

    return Object.values(filters).some((value) => {
      if (Array.isArray(value)) {
        return value.length > 0;
      }
      return value !== undefined && value !== null && value !== '';
    });
  }, [searchCriteria]);

  return {
    // State
    searchCriteria,
    searchResults: searchMutation.data,
    isLoading: searchMutation.isPending,
    error: searchMutation.error,
    hasSearched,
    searchOptions,

    // Actions
    updateCriteria,
    executeSearch,
    resetCriteria,
    loadSavedSearch,
    updatePagination,

    // Helpers
    hasActiveFilters: hasActiveFilters(),
    isSearchValid: hasActiveFilters(),
  };
}
