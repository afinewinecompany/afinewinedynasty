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

  const fetchRankings = useCallback(
    async (abortSignal?: AbortSignal) => {
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
        // Note: This endpoint can be slow (30-50s) on first request due to complex queries
        // Backend caches results, so subsequent requests are fast
        const result = await apiClient.get<CompositeRankingsResponse>(
          endpoint,
          30,
          { timeout: 60000, signal: abortSignal } // 60 second timeout for initial query
        );

        setData(result);
      } catch (err: any) {
        // Ignore abort errors - these are expected when component unmounts
        if (err?.name === 'AbortError') {
          console.log('[useCompositeRankings] Request aborted (expected during cleanup)');
          return;
        }

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
    },
    [
      params.page,
      params.page_size,
      params.position,
      params.organization,
      params.limit,
    ]
  );

  useEffect(() => {
    const controller = new AbortController();

    fetchRankings(controller.signal);

    // Cleanup: abort the request when component unmounts or dependencies change
    return () => {
      controller.abort();
    };
  }, [fetchRankings]);

  const refetch = useCallback(() => {
    // Create a new abort controller for manual refetch
    const controller = new AbortController();
    fetchRankings(controller.signal);
  }, [fetchRankings]);

  return { data, loading, error, refetch };
}
