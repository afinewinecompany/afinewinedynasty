import { useState, useEffect, useCallback } from 'react';
import { ProspectProfile } from '@/types/prospect';
import { apiClient } from '@/lib/api/client';

export function useProspectProfile(id: string) {
  const [data, setData] = useState<ProspectProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchProspectProfile = useCallback(async () => {
    if (!id) return;

    try {
      setLoading(true);
      setError(null);

      const endpoint = `/prospects/${id}`;

      // Cache prospect profiles for 1 hour as per story requirements
      const result = await apiClient.get<ProspectProfile>(endpoint, 60);

      setData(result);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to fetch prospect profile'
      );
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchProspectProfile();
  }, [fetchProspectProfile]);

  const refetch = useCallback(() => {
    fetchProspectProfile();
  }, [fetchProspectProfile]);

  return { data, loading, error, refetch };
}
