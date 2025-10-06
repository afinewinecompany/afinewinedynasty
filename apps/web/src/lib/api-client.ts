/**
 * API client with authentication and token refresh
 */

import { getAccessToken, refreshAccessToken, isTokenExpired, clearTokens } from './auth';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const API_VERSION = process.env.NEXT_PUBLIC_API_VERSION || 'v1';
const BASE_URL = `${API_URL}/api/${API_VERSION}`;

interface RequestOptions extends RequestInit {
  skipAuth?: boolean;
}

/**
 * Make authenticated API request with automatic token refresh
 */
export async function apiRequest<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const { skipAuth = false, ...fetchOptions } = options;

  // Prepare headers
  const headers = new Headers(fetchOptions.headers);
  headers.set('Content-Type', 'application/json');

  // Add auth token if not skipping auth
  if (!skipAuth) {
    // Check if token is expired and refresh if needed
    if (isTokenExpired()) {
      const newTokens = await refreshAccessToken();
      if (!newTokens) {
        // Refresh failed, redirect to login
        if (typeof window !== 'undefined') {
          window.location.href = '/login';
        }
        throw new Error('Authentication required');
      }
    }

    const token = getAccessToken();
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
    }
  }

  // Make request
  const url = `${BASE_URL}${endpoint}`;
  const response = await fetch(url, {
    ...fetchOptions,
    headers,
  });

  // Handle 401 Unauthorized - try token refresh once
  if (response.status === 401 && !skipAuth) {
    const newTokens = await refreshAccessToken();
    if (newTokens) {
      // Retry request with new token
      headers.set('Authorization', `Bearer ${newTokens.access_token}`);
      const retryResponse = await fetch(url, {
        ...fetchOptions,
        headers,
      });

      if (!retryResponse.ok) {
        throw await handleErrorResponse(retryResponse);
      }

      return retryResponse.json();
    } else {
      // Refresh failed, redirect to login
      clearTokens();
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
      throw new Error('Authentication required');
    }
  }

  // Handle other error responses
  if (!response.ok) {
    throw await handleErrorResponse(response);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return null as T;
  }

  // Parse JSON response
  return response.json();
}

/**
 * Handle error responses
 */
async function handleErrorResponse(response: Response): Promise<Error> {
  let errorMessage = `HTTP ${response.status}: ${response.statusText}`;

  try {
    const errorData = await response.json();
    errorMessage = errorData.detail || errorMessage;
  } catch {
    // Failed to parse error JSON, use default message
  }

  return new Error(errorMessage);
}

/**
 * API methods
 */
export const api = {
  // GET request
  get: <T>(endpoint: string, options?: RequestOptions) =>
    apiRequest<T>(endpoint, { ...options, method: 'GET' }),

  // POST request
  post: <T>(endpoint: string, data?: any, options?: RequestOptions) =>
    apiRequest<T>(endpoint, {
      ...options,
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    }),

  // PUT request
  put: <T>(endpoint: string, data?: any, options?: RequestOptions) =>
    apiRequest<T>(endpoint, {
      ...options,
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    }),

  // PATCH request
  patch: <T>(endpoint: string, data?: any, options?: RequestOptions) =>
    apiRequest<T>(endpoint, {
      ...options,
      method: 'PATCH',
      body: data ? JSON.stringify(data) : undefined,
    }),

  // DELETE request
  delete: <T>(endpoint: string, options?: RequestOptions) =>
    apiRequest<T>(endpoint, { ...options, method: 'DELETE' }),
};

/**
 * Lineup API methods
 */
export const lineupApi = {
  // Get all user lineups
  getLineups: (skip = 0, limit = 100) =>
    api.get(`/lineups?skip=${skip}&limit=${limit}`),

  // Get lineup by ID with prospects
  getLineup: (lineupId: number) =>
    api.get(`/lineups/${lineupId}`),

  // Create lineup
  createLineup: (data: { name: string; description?: string; lineup_type?: string }) =>
    api.post('/lineups', data),

  // Update lineup
  updateLineup: (lineupId: number, data: { name?: string; description?: string }) =>
    api.put(`/lineups/${lineupId}`, data),

  // Delete lineup
  deleteLineup: (lineupId: number) =>
    api.delete(`/lineups/${lineupId}`),

  // Add prospect to lineup
  addProspect: (lineupId: number, prospectId: number, data?: { position?: string; rank?: number; notes?: string }) =>
    api.post(`/lineups/${lineupId}/prospects`, {
      prospect_id: prospectId,
      ...data,
    }),

  // Update prospect in lineup
  updateProspect: (lineupId: number, prospectId: number, data: { position?: string; rank?: number; notes?: string }) =>
    api.put(`/lineups/${lineupId}/prospects/${prospectId}`, data),

  // Remove prospect from lineup
  removeProspect: (lineupId: number, prospectId: number) =>
    api.delete(`/lineups/${lineupId}/prospects/${prospectId}`),

  // Bulk add prospects
  bulkAddProspects: (lineupId: number, prospectIds: number[]) =>
    api.post(`/lineups/${lineupId}/prospects/bulk`, { prospect_ids: prospectIds }),

  // Sync Fantrax league
  syncFantrax: (leagueId: number, lineupName?: string) =>
    api.post('/lineups/sync/fantrax', { league_id: leagueId, lineup_name: lineupName }),
};
