import { useState, useCallback } from 'react';
import { apiClient } from '@/lib/api/client';
import debounce from 'lodash/debounce';

export interface ProspectSearchSuggestion {
  name: string;
  organization: string | null;
  position: string;
  display: string;
}

export function useProspectSearch() {
  const [suggestions, setSuggestions] = useState<ProspectSearchSuggestion[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const fetchSuggestions = useCallback(async (query: string) => {
    if (!query || query.length < 1) {
      setSuggestions([]);
      return;
    }

    setIsLoading(true);
    try {
      const response = await apiClient.get('/api/v1/prospects/search/autocomplete', {
        params: { q: query, limit: 5 }
      });
      setSuggestions(response.data);
    } catch (error) {
      console.error('Failed to fetch suggestions:', error);
      setSuggestions([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const debouncedFetch = useCallback(
    debounce(fetchSuggestions, 300),
    []
  );

  const getSuggestions = useCallback((query: string) => {
    debouncedFetch(query);
  }, [debouncedFetch]);

  const clearSuggestions = useCallback(() => {
    setSuggestions([]);
  }, []);

  return {
    suggestions,
    isLoading,
    getSuggestions,
    clearSuggestions
  };
}
