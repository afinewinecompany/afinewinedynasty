import { useState, useEffect, useCallback } from 'react';
import { ProspectListParams, ProspectListResponse } from '@/types/prospect';
import { apiClient } from '@/lib/api/client';

export function useProspects(params: ProspectListParams = {}) {
  const [data, setData] = useState<ProspectListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchProspects = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const searchParams = new URLSearchParams();
      if (params.page) searchParams.set('page', params.page.toString());
      if (params.limit) searchParams.set('limit', params.limit.toString());
      if (params.position) searchParams.set('position', params.position);
      if (params.organization)
        searchParams.set('organization', params.organization);
      if (params.sort_by) searchParams.set('sort_by', params.sort_by);
      if (params.sort_order) searchParams.set('sort_order', params.sort_order);
      if (params.search) searchParams.set('search', params.search);

      const endpoint = `/prospects?${searchParams}`;

      // Cache rankings for 30 minutes as per story requirements
      const result = await apiClient.get<ProspectListResponse>(endpoint, 30);

      setData(result);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to fetch prospects'
      );
    } finally {
      setLoading(false);
    }
  }, [
    params.page,
    params.limit,
    params.position,
    params.organization,
    params.sort_by,
    params.sort_order,
    params.search,
  ]);

  useEffect(() => {
    fetchProspects();
  }, [fetchProspects]);

  const refetch = useCallback(() => {
    fetchProspects();
  }, [fetchProspects]);

  return { data, loading, error, refetch };
}
