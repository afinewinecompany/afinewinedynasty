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
      const response = await apiClient.get('/api/v1/prospects', {
        params: {
          page: params.page,
          page_size: params.pageSize,
          limit: params.limit,
          position: params.position,
          organization: params.organization,
          level: params.level,
          eta_min: params.etaMin,
          eta_max: params.etaMax,
          age_min: params.ageMin,
          age_max: params.ageMax,
          search: params.search,
          sort_by: params.sortBy,
          sort_order: params.sortOrder,
        },
      });
      return response.data;
    },
    staleTime: 30 * 60 * 1000, // 30 minutes
    cacheTime: 60 * 60 * 1000, // 1 hour
    keepPreviousData: true,
  });
}
