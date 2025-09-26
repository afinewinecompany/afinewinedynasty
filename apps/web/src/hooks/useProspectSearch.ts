import { useState, useCallback } from 'react';
import { Prospect } from '@/types/prospect';
import { apiClient } from '@/lib/api/client';

export interface ProspectSearchResult {
  prospects: Prospect[];
  total: number;
}

export function useProspectSearch() {
  const [results, setResults] = useState<ProspectSearchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const search = useCallback(async (query: string) => {
    if (!query.trim()) {
      setResults(null);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const endpoint = `/api/prospects/search?q=${encodeURIComponent(
        query
      )}&limit=10`;

      // Cache search results for 10 minutes
      const result = await apiClient.get<ProspectSearchResult>(endpoint, 10);

      setResults(result);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to search prospects'
      );
      setResults(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const clearSearch = useCallback(() => {
    setResults(null);
    setError(null);
  }, []);

  return { results, loading, error, search, clearSearch };
}
