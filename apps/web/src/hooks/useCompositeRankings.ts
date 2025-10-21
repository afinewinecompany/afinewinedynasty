import { useState, useEffect, useCallback } from 'react';
import {
  CompositeRankingsParams,
  CompositeRankingsResponse,
} from '@/types/prospect';
import { apiClient } from '@/lib/api/client';

export function useCompositeRankings(params: CompositeRankingsParams = {}) {
  const [data, setData] = useState<CompositeRankingsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchRankings = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const searchParams = new URLSearchParams();
      if (params.page) searchParams.set('page', params.page.toString());
      if (params.page_size)
        searchParams.set('page_size', params.page_size.toString());
      if (params.position) searchParams.set('position', params.position);
      if (params.organization)
        searchParams.set('organization', params.organization);
      if (params.limit) searchParams.set('limit', params.limit.toString());

      const endpoint = `/prospects/composite-rankings?${searchParams}`;

      // Cache rankings for 30 minutes (same as backend)
      const result = await apiClient.get<CompositeRankingsResponse>(
        endpoint,
        30
      );

      setData(result);
    } catch (err) {
      console.error('[useCompositeRankings] API Error:', err);
      console.error('[useCompositeRankings] Error details:', {
        message: err instanceof Error ? err.message : 'Unknown error',
        stack: err instanceof Error ? err.stack : undefined,
        raw: err
      });
      setError(
        err instanceof Error
          ? err.message
          : 'Failed to fetch composite rankings'
      );
    } finally {
      setLoading(false);
    }
  }, [
    params.page,
    params.page_size,
    params.position,
    params.organization,
    params.limit,
  ]);

  useEffect(() => {
    fetchRankings();
  }, [fetchRankings]);

  const refetch = useCallback(() => {
    fetchRankings();
  }, [fetchRankings]);

  return { data, loading, error, refetch };
}
