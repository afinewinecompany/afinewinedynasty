import { ProspectRankingsParams } from '@/types/prospect';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const API_VERSION = process.env.NEXT_PUBLIC_API_VERSION || 'v1';
const BASE_URL = `${API_URL}/api/${API_VERSION}`;

export async function exportProspectsCsv(params: ProspectRankingsParams) {
  // Build query params
  const searchParams = new URLSearchParams();
  if (params.position) searchParams.set('position', params.position.toString());
  if (params.organization) searchParams.set('organization', params.organization.toString());
  if (params.level) searchParams.set('level', params.level.toString());
  if (params.etaMin) searchParams.set('eta_min', params.etaMin.toString());
  if (params.etaMax) searchParams.set('eta_max', params.etaMax.toString());
  if (params.ageMin) searchParams.set('age_min', params.ageMin.toString());
  if (params.ageMax) searchParams.set('age_max', params.ageMax.toString());
  if (params.search) searchParams.set('search', params.search);

  // Fetch CSV as blob
  const url = `${BASE_URL}/prospects/export/csv?${searchParams}`;
  const response = await fetch(url, {
    headers: {
      'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
    },
  });

  if (!response.ok) {
    throw new Error('Failed to export CSV');
  }

  // Create download link
  const blob = await response.blob();
  const downloadUrl = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = downloadUrl;

  // Extract filename from Content-Disposition header or use default
  const contentDisposition = response.headers.get('content-disposition');
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
  window.URL.revokeObjectURL(downloadUrl);
}
