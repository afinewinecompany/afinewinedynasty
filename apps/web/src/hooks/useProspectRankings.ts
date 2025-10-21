import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import {
  ProspectRankingsResponse,
  ProspectRankingsParams,
} from '@/types/prospect';

export function useProspectRankings(params: ProspectRankingsParams) {
  return useQuery<ProspectRankingsResponse>({
    queryKey: ['prospect-rankings', params],
    queryFn: async () => {
      const searchParams = new URLSearchParams();
      if (params.page) searchParams.set('page', params.page.toString());
      if (params.pageSize) searchParams.set('page_size', params.pageSize.toString());
      if (params.limit) searchParams.set('limit', params.limit.toString());
      if (params.position) searchParams.set('position', params.position.toString());
      if (params.organization) searchParams.set('organization', params.organization.toString());
      if (params.level) searchParams.set('level', params.level.toString());
      if (params.etaMin) searchParams.set('eta_min', params.etaMin.toString());
      if (params.etaMax) searchParams.set('eta_max', params.etaMax.toString());
      if (params.ageMin) searchParams.set('age_min', params.ageMin.toString());
      if (params.ageMax) searchParams.set('age_max', params.ageMax.toString());
      if (params.search) searchParams.set('search', params.search);
      if (params.sortBy) searchParams.set('sort_by', params.sortBy);
      if (params.sortOrder) searchParams.set('sort_order', params.sortOrder);

      const response = await apiClient.get<ProspectRankingsResponse>(
        `/prospects?${searchParams}`,
        30 // Cache for 30 minutes
      );
      return response;
    },
    staleTime: 30 * 60 * 1000, // 30 minutes
    cacheTime: 60 * 60 * 1000, // 1 hour
    keepPreviousData: true,
  });
}
