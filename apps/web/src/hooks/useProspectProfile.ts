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

      const endpoint = `/prospects/${id}/profile`;

      // Cache prospect profiles for 1 hour as per story requirements
      const result = await apiClient.get<any>(endpoint, 60);

      // Transform the API response to ProspectProfile format
      const profile: ProspectProfile = {
        id: result.prospect.id,
        mlb_id: result.prospect.mlb_id,
        name: result.prospect.name,
        position: result.prospect.position,
        organization: result.prospect.organization,
        level: result.prospect.level,
        age: result.prospect.age,
        eta_year: result.prospect.eta_year,
        stats: result.stats?.history,
        ml_prediction: result.ml_prediction,
        dynasty_metrics: result.dynasty_metrics,
        scouting_grades: result.scouting_grades?.[0],
        pitch_metrics: result.pitch_metrics
      };

      setData(profile);
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
