import { apiClient } from './client';
import { ProspectRankingsParams } from '@/types/prospect';

export async function exportProspectsCsv(params: ProspectRankingsParams) {
  const response = await apiClient.get('/api/v1/prospects/export/csv', {
    params: {
      position: params.position,
      organization: params.organization,
      level: params.level,
      eta_min: params.etaMin,
      eta_max: params.etaMax,
      age_min: params.ageMin,
      age_max: params.ageMax,
      search: params.search
    },
    responseType: 'blob'
  });

  // Create a download link
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;

  // Extract filename from Content-Disposition header or use default
  const contentDisposition = response.headers['content-disposition'];
  let filename = 'prospect_rankings.csv';
  if (contentDisposition) {
    const filenameMatch = contentDisposition.match(/filename="(.+)"/);
    if (filenameMatch) {
      filename = filenameMatch[1];
    }
  }

  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  link.parentNode?.removeChild(link);
  window.URL.revokeObjectURL(url);
}