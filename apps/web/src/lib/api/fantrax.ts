/**
 * Fantrax API client utilities
 *
 * Provides functions for interacting with Fantrax integration endpoints
 * including OAuth, roster sync, and recommendations.
 *
 * @module lib/api/fantrax
 * @since 1.0.0
 */

import type {
  OAuthAuthResponse,
  OAuthCallbackResponse,
  FantraxLeague,
  RosterData,
  RosterSyncRequest,
  RosterSyncResponse,
  TeamAnalysis,
  ProspectRecommendation,
  TradeAnalysisRequest,
  TradeAnalysisResponse,
  ConnectionStatus,
} from '@/types/fantrax';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
const FANTRAX_BASE = `${API_BASE_URL}/integrations/fantrax`;

/**
 * Get authorization headers with JWT token
 *
 * @returns Authorization headers object
 *
 * @since 1.0.0
 */
function getAuthHeaders(): HeadersInit {
  const token = localStorage.getItem('access_token');
  return {
    'Content-Type': 'application/json',
    ...(token && { Authorization: `Bearer ${token}` }),
  };
}

/**
 * Handle API response errors
 *
 * @param response - Fetch response object
 * @throws Error with API error message
 *
 * @since 1.0.0
 */
async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error = await response.json().catch(() => ({
      detail: `HTTP ${response.status}: ${response.statusText}`,
    }));
    throw new Error(error.detail || 'An error occurred');
  }
  return response.json();
}

/**
 * Get Fantrax OAuth authorization URL
 *
 * Initiates the OAuth flow by retrieving the authorization URL
 * that the user should be redirected to.
 *
 * @returns Promise resolving to OAuth authorization data
 * @throws Error if request fails
 *
 * @example
 * ```typescript
 * const { authorization_url, state } = await getAuthorizationUrl();
 * window.location.href = authorization_url;
 * ```
 *
 * @since 1.0.0
 */
export async function getAuthorizationUrl(): Promise<OAuthAuthResponse> {
  const response = await fetch(`${FANTRAX_BASE}/auth`, {
    method: 'GET',
    headers: getAuthHeaders(),
  });
  return handleResponse<OAuthAuthResponse>(response);
}

/**
 * Handle Fantrax OAuth callback
 *
 * Processes the OAuth callback after user authorizes the application.
 *
 * @param code - Authorization code from Fantrax
 * @param state - State token for CSRF validation
 * @returns Promise resolving to callback response
 * @throws Error if callback processing fails
 *
 * @since 1.0.0
 */
export async function handleOAuthCallback(
  code: string,
  state: string
): Promise<OAuthCallbackResponse> {
  const response = await fetch(`${FANTRAX_BASE}/callback`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({ code, state }),
  });
  return handleResponse<OAuthCallbackResponse>(response);
}

/**
 * Disconnect Fantrax integration
 *
 * Revokes access and removes stored tokens.
 *
 * @returns Promise resolving to success status
 * @throws Error if disconnection fails
 *
 * @since 1.0.0
 */
export async function disconnectFantrax(): Promise<{ success: boolean; message: string }> {
  const response = await fetch(`${FANTRAX_BASE}/disconnect`, {
    method: 'POST',
    headers: getAuthHeaders(),
  });
  return handleResponse<{ success: boolean; message: string }>(response);
}

/**
 * Get user's Fantrax leagues
 *
 * Retrieves all leagues the user participates in on Fantrax.
 *
 * @returns Promise resolving to array of leagues
 * @throws Error if request fails
 *
 * @performance
 * - Cached on server for 24 hours
 * - Typical response time: 200-500ms
 *
 * @since 1.0.0
 */
export async function getUserLeagues(): Promise<FantraxLeague[]> {
  const response = await fetch(`${FANTRAX_BASE}/leagues`, {
    method: 'GET',
    headers: getAuthHeaders(),
  });
  return handleResponse<FantraxLeague[]>(response);
}

/**
 * Sync roster for a specific league
 *
 * Fetches and stores the current roster from Fantrax.
 *
 * @param request - Roster sync request with league ID
 * @returns Promise resolving to sync response
 * @throws Error if sync fails
 *
 * @performance
 * - Response time: 2-5 seconds for typical 40-player roster
 * - Results cached for 1 hour unless force_refresh is true
 *
 * @since 1.0.0
 */
export async function syncRoster(request: RosterSyncRequest): Promise<RosterSyncResponse> {
  const response = await fetch(`${FANTRAX_BASE}/roster/sync`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(request),
  });
  return handleResponse<RosterSyncResponse>(response);
}

/**
 * Get cached roster for a league
 *
 * Retrieves the most recently synced roster data.
 *
 * @param leagueId - League ID to get roster for
 * @returns Promise resolving to roster data
 * @throws Error if roster not found or request fails
 *
 * @performance
 * - Response time: <100ms (from cache)
 *
 * @since 1.0.0
 */
export async function getRoster(leagueId: string): Promise<RosterData> {
  const response = await fetch(`${FANTRAX_BASE}/roster/${leagueId}`, {
    method: 'GET',
    headers: getAuthHeaders(),
  });
  return handleResponse<RosterData>(response);
}

/**
 * Get team needs analysis
 *
 * Analyzes the team roster to identify strengths, weaknesses,
 * and future roster holes.
 *
 * @param leagueId - League ID to analyze
 * @returns Promise resolving to team analysis
 * @throws Error if analysis fails
 *
 * @performance
 * - Response time: 500-1000ms
 * - Cached for 1 hour
 *
 * @since 1.0.0
 */
export async function getTeamAnalysis(leagueId: string): Promise<TeamAnalysis> {
  const response = await fetch(`${FANTRAX_BASE}/analysis/${leagueId}`, {
    method: 'GET',
    headers: getAuthHeaders(),
  });
  return handleResponse<TeamAnalysis>(response);
}

/**
 * Get personalized prospect recommendations
 *
 * Returns prospects that best fit the team's needs and timeline.
 *
 * @param leagueId - League ID for recommendations
 * @param limit - Maximum number of recommendations (default: 10)
 * @returns Promise resolving to prospect recommendations
 * @throws Error if request fails
 *
 * @performance
 * - Response time: 1-2 seconds
 * - Cached for 30 minutes
 *
 * @since 1.0.0
 */
export async function getRecommendations(
  leagueId: string,
  limit: number = 10
): Promise<ProspectRecommendation[]> {
  const response = await fetch(
    `${FANTRAX_BASE}/recommendations/${leagueId}?limit=${limit}`,
    {
      method: 'GET',
      headers: getAuthHeaders(),
    }
  );
  return handleResponse<ProspectRecommendation[]>(response);
}

/**
 * Analyze a potential trade
 *
 * Evaluates a trade based on team needs and prospect values.
 *
 * @param request - Trade analysis request
 * @returns Promise resolving to trade analysis
 * @throws Error if analysis fails
 *
 * @performance
 * - Response time: 1-2 seconds
 * - Complex calculation with multiple data sources
 *
 * @since 1.0.0
 */
export async function analyzeTrade(
  request: TradeAnalysisRequest
): Promise<TradeAnalysisResponse> {
  const response = await fetch(`${FANTRAX_BASE}/trade-analysis`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(request),
  });
  return handleResponse<TradeAnalysisResponse>(response);
}

/**
 * Check Fantrax connection status
 *
 * Verifies if user has active Fantrax connection.
 *
 * @returns Promise resolving to connection status
 * @throws Error if request fails
 *
 * @since 1.0.0
 */
export async function getConnectionStatus(): Promise<ConnectionStatus> {
  try {
    const leagues = await getUserLeagues();
    return {
      connected: true,
      leagues_count: leagues.length,
    };
  } catch (error) {
    return {
      connected: false,
    };
  }
}
