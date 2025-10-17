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

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL
  ? `${process.env.NEXT_PUBLIC_API_URL}/api/v1`
  : 'http://localhost:8000/api/v1';
const FANTRAX_BASE = `${API_BASE_URL}/integrations/fantrax`;
const FANTRAX_AUTH_BASE = `${API_BASE_URL}/fantrax/auth`;
const FANTRAX_SECRET_API_BASE = `${API_BASE_URL}/fantrax`; // New Secret ID API

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

// ============================================================================
// In-Browser Authentication (New)
// ============================================================================

/**
 * Authentication initiate response
 */
export interface AuthInitiateResponse {
  session_id: string;
  status_url: string;
  expires_in: number;
  message: string;
}

/**
 * Authentication status response
 */
export interface AuthStatusResponse {
  session_id: string;
  status: string;
  current_url: string | null;
  elapsed_seconds: number;
  expires_in: number;
  message: string;
}

/**
 * Authentication complete response
 */
export interface AuthCompleteResponse {
  success: boolean;
  message: string;
  connected_at: string;
}

/**
 * Authentication cancel response
 */
export interface AuthCancelResponse {
  success: boolean;
  message: string;
}

/**
 * Initiate in-browser Fantrax authentication
 *
 * Starts server-side Selenium session for authentication.
 *
 * @returns Promise resolving to session information
 * @throws Error if user not premium or rate limit exceeded
 *
 * @example
 * ```typescript
 * const response = await initiateAuth();
 * // Poll status with response.session_id
 * ```
 *
 * @since 1.0.0
 */
export async function initiateAuth(): Promise<AuthInitiateResponse> {
  const response = await fetch(`${FANTRAX_AUTH_BASE}/initiate`, {
    method: 'POST',
    headers: getAuthHeaders(),
  });
  return handleResponse<AuthInitiateResponse>(response);
}

/**
 * Get authentication session status
 *
 * Polls current status of Selenium authentication session.
 * Should be called every 2 seconds.
 *
 * @param sessionId - Session identifier from initiate
 * @returns Promise resolving to current status
 * @throws Error if session not found or expired
 *
 * @since 1.0.0
 */
export async function getAuthStatus(sessionId: string): Promise<AuthStatusResponse> {
  const response = await fetch(`${FANTRAX_AUTH_BASE}/status/${sessionId}`, {
    method: 'GET',
    headers: getAuthHeaders(),
  });
  return handleResponse<AuthStatusResponse>(response);
}

/**
 * Complete authentication
 *
 * Captures cookies and stores in database.
 *
 * @param sessionId - Session identifier
 * @returns Promise resolving to completion response
 * @throws Error if cookie capture fails
 *
 * @since 1.0.0
 */
export async function completeAuth(sessionId: string): Promise<AuthCompleteResponse> {
  const response = await fetch(`${FANTRAX_AUTH_BASE}/complete/${sessionId}`, {
    method: 'POST',
    headers: getAuthHeaders(),
  });
  return handleResponse<AuthCompleteResponse>(response);
}

/**
 * Cancel authentication session
 *
 * Stops Selenium browser and cleans up resources.
 *
 * @param sessionId - Session identifier
 * @returns Promise resolving to cancellation response
 *
 * @since 1.0.0
 */
export async function cancelAuth(sessionId: string): Promise<AuthCancelResponse> {
  const response = await fetch(`${FANTRAX_AUTH_BASE}/cancel/${sessionId}`, {
    method: 'DELETE',
    headers: getAuthHeaders(),
  });
  return handleResponse<AuthCancelResponse>(response);
}

// ============================================================================
// OAuth Authentication (Legacy - kept for reference)
// ============================================================================

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
 * @deprecated Use initiateAuth() for in-browser authentication instead
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
export async function disconnectFantrax(): Promise<{
  success: boolean;
  message: string;
}> {
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
export async function syncRoster(
  request: RosterSyncRequest
): Promise<RosterSyncResponse> {
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
    const response = await fetch(`${FANTRAX_SECRET_API_BASE}/status`, {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse<ConnectionStatus>(response);
  } catch (error) {
    return {
      connected: false,
    };
  }
}

// ============================================================================
// Secret ID API (New - Official Fantrax API)
// ============================================================================

/**
 * Connect Fantrax Response
 */
export interface ConnectFantraxResponse {
  connected: boolean;
  connected_at: string | null;
  leagues_count: number | null;
}

/**
 * League Response from Secret ID API
 */
export interface SecretAPILeague {
  league_id: string;
  name: string;
  sport: string | null;
  teams: Array<{
    team_id: string;
    team_name: string;
  }>;
  is_active: boolean; // Whether user has selected this league
}

/**
 * League Info Response
 */
export interface LeagueInfoResponse {
  league_id: string;
  name: string;
  sport: string | null;
  teams: any[];
  matchups: any[];
  players: any[];
  settings: any;
  current_period: number | null;
  season: number | null;
}

/**
 * Roster Response
 */
export interface RosterResponse {
  league_id: string;
  period: number | null;
  rosters: any[];
}

/**
 * Standings Response
 */
export interface StandingsResponse {
  league_id: string;
  standings: any[];
}

/**
 * Connect Fantrax account using Secret ID
 *
 * @param secretId - User's Fantrax Secret ID from their profile
 * @returns Promise resolving to connection response
 * @throws Error if connection fails
 *
 * @example
 * ```typescript
 * const response = await connectWithSecretId('24pscnquxwekzngy');
 * console.log(`Connected with ${response.leagues_count} leagues`);
 * ```
 *
 * @since 2.0.0
 */
export async function connectWithSecretId(
  secretId: string
): Promise<ConnectFantraxResponse> {
  const response = await fetch(`${FANTRAX_SECRET_API_BASE}/connect`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({ secret_id: secretId }),
  });
  return handleResponse<ConnectFantraxResponse>(response);
}

/**
 * Get Fantrax connection status (Secret ID API)
 *
 * @returns Promise resolving to connection status
 * @throws Error if request fails
 *
 * @since 2.0.0
 */
export async function getSecretAPIStatus(): Promise<ConnectFantraxResponse> {
  const response = await fetch(`${FANTRAX_SECRET_API_BASE}/status`, {
    method: 'GET',
    headers: getAuthHeaders(),
  });
  return handleResponse<ConnectFantraxResponse>(response);
}

/**
 * Disconnect Fantrax account (Secret ID API)
 *
 * @returns Promise resolving to success message
 * @throws Error if disconnection fails
 *
 * @since 2.0.0
 */
export async function disconnectSecretAPI(): Promise<{ message: string }> {
  const response = await fetch(`${FANTRAX_SECRET_API_BASE}/disconnect`, {
    method: 'DELETE',
    headers: getAuthHeaders(),
  });
  return handleResponse<{ message: string }>(response);
}

/**
 * Get user's leagues using Secret ID API
 *
 * @returns Promise resolving to array of leagues
 * @throws Error if request fails
 *
 * @since 2.0.0
 */
export async function getSecretAPILeagues(): Promise<SecretAPILeague[]> {
  const response = await fetch(`${FANTRAX_SECRET_API_BASE}/leagues`, {
    method: 'GET',
    headers: getAuthHeaders(),
  });
  return handleResponse<SecretAPILeague[]>(response);
}

/**
 * Get detailed league information using Secret ID API
 *
 * @param leagueId - Fantrax League ID
 * @returns Promise resolving to league info
 * @throws Error if request fails
 *
 * @since 2.0.0
 */
export async function getSecretAPILeagueInfo(
  leagueId: string
): Promise<LeagueInfoResponse> {
  const response = await fetch(
    `${FANTRAX_SECRET_API_BASE}/leagues/${leagueId}`,
    {
      method: 'GET',
      headers: getAuthHeaders(),
    }
  );
  return handleResponse<LeagueInfoResponse>(response);
}

/**
 * Get team rosters for a league using Secret ID API
 *
 * @param leagueId - Fantrax League ID
 * @param period - Optional lineup period
 * @returns Promise resolving to rosters
 * @throws Error if request fails
 *
 * @since 2.0.0
 */
export async function getSecretAPIRosters(
  leagueId: string,
  period?: number
): Promise<RosterResponse> {
  const url = period
    ? `${FANTRAX_SECRET_API_BASE}/leagues/${leagueId}/rosters?period=${period}`
    : `${FANTRAX_SECRET_API_BASE}/leagues/${leagueId}/rosters`;

  const response = await fetch(url, {
    method: 'GET',
    headers: getAuthHeaders(),
  });
  return handleResponse<RosterResponse>(response);
}

/**
 * Get enriched team roster with full player information
 *
 * Combines roster data (contracts) with league player pool (names, teams, ages)
 * to provide complete player information.
 *
 * @param leagueId - Fantrax League ID
 * @param teamId - Team ID
 * @param period - Optional lineup period
 * @returns Promise resolving to enriched roster
 * @throws Error if request fails
 *
 * @since 2.0.0
 */
export async function getEnrichedRoster(
  leagueId: string,
  teamId: string,
  period?: number
): Promise<any> {
  const url = period
    ? `${FANTRAX_SECRET_API_BASE}/leagues/${leagueId}/rosters/${teamId}/enriched?period=${period}`
    : `${FANTRAX_SECRET_API_BASE}/leagues/${leagueId}/rosters/${teamId}/enriched`;

  const response = await fetch(url, {
    method: 'GET',
    headers: getAuthHeaders(),
  });
  return handleResponse<any>(response);
}

/**
 * Get league standings using Secret ID API
 *
 * @param leagueId - Fantrax League ID
 * @returns Promise resolving to standings
 * @throws Error if request fails
 *
 * @since 2.0.0
 */
export async function getSecretAPIStandings(
  leagueId: string
): Promise<StandingsResponse> {
  const response = await fetch(
    `${FANTRAX_SECRET_API_BASE}/leagues/${leagueId}/standings`,
    {
      method: 'GET',
      headers: getAuthHeaders(),
    }
  );
  return handleResponse<StandingsResponse>(response);
}

/**
 * Get draft results using Secret ID API
 *
 * @param leagueId - Fantrax League ID
 * @returns Promise resolving to draft results
 * @throws Error if request fails
 *
 * @since 2.0.0
 */
export async function getSecretAPIDraftResults(leagueId: string): Promise<any> {
  const response = await fetch(
    `${FANTRAX_SECRET_API_BASE}/leagues/${leagueId}/draft-results`,
    {
      method: 'GET',
      headers: getAuthHeaders(),
    }
  );
  return handleResponse<any>(response);
}

/**
 * Update league selections
 *
 * Updates which leagues are selected/active for the user.
 * Selected leagues will be available in the My League page.
 *
 * @param leagueIds - Array of league IDs to mark as selected
 * @returns Promise resolving to success response
 * @throws Error if update fails
 *
 * @example
 * ```typescript
 * await updateLeagueSelections(['league_123', 'league_456']);
 * ```
 *
 * @since 2.0.0
 */
export async function updateLeagueSelections(
  leagueIds: string[]
): Promise<{ success: boolean; message: string; selected_count: number }> {
  const response = await fetch(`${FANTRAX_SECRET_API_BASE}/leagues/select`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({ league_ids: leagueIds }),
  });
  return handleResponse<{
    success: boolean;
    message: string;
    selected_count: number;
  }>(response);
}

/**
 * Update team selection for a league
 *
 * Manually specifies which team belongs to the user in a league.
 * This solves issues where automatic team detection fails.
 *
 * @param leagueId - The league ID
 * @param teamId - The team ID that belongs to the user
 * @param teamName - The team name for display
 * @returns Promise resolving to success response
 * @throws Error if update fails
 *
 * @example
 * ```typescript
 * await updateTeamSelection('league_123', 'team_456', 'My Awesome Team');
 * ```
 *
 * @since 2.0.0
 */
export async function updateTeamSelection(
  leagueId: string,
  teamId: string,
  teamName: string
): Promise<{
  success: boolean;
  message: string;
  league_id: string;
  team_id: string;
  team_name: string;
}> {
  const response = await fetch(`${FANTRAX_SECRET_API_BASE}/leagues/team-selection`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({
      league_id: leagueId,
      team_id: teamId,
      team_name: teamName,
    }),
  });
  return handleResponse<{
    success: boolean;
    message: string;
    league_id: string;
    team_id: string;
    team_name: string;
  }>(response);
}

/**
 * Save synced roster to database
 *
 * Persists roster data so it can be viewed later without re-syncing.
 *
 * @param leagueId - The league ID
 * @param rosterData - Roster data to save
 * @returns Promise resolving to success response
 * @throws Error if save fails
 *
 * @example
 * ```typescript
 * await saveRoster('league_123', {
 *   league_id: 'league_123',
 *   team_id: 'team_456',
 *   team_name: 'Athletics',
 *   players: [...]
 * });
 * ```
 *
 * @since 2.0.0
 */
export async function saveRoster(
  leagueId: string,
  rosterData: {
    league_id: string;
    team_id: string;
    team_name: string;
    players: any[];
  }
): Promise<{
  success: boolean;
  message: string;
  players_saved: number;
}> {
  const response = await fetch(
    `${FANTRAX_SECRET_API_BASE}/leagues/${leagueId}/rosters/save`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(rosterData),
    }
  );
  return handleResponse<{
    success: boolean;
    message: string;
    players_saved: number;
  }>(response);
}

/**
 * Get saved roster from database
 *
 * Retrieves the last synced roster for a league.
 *
 * @param leagueId - The league ID
 * @returns Promise resolving to saved roster data
 * @throws Error if retrieval fails or roster not found
 *
 * @example
 * ```typescript
 * const roster = await getSavedRoster('league_123');
 * console.log(`Loaded ${roster.players.length} players`);
 * ```
 *
 * @since 2.0.0
 */
export async function getSavedRoster(leagueId: string): Promise<{
  league_id: string;
  team_id: string;
  team_name: string;
  players: any[];
  last_updated: string | null;
}> {
  const response = await fetch(
    `${FANTRAX_SECRET_API_BASE}/leagues/${leagueId}/rosters/saved`,
    {
      method: 'GET',
      headers: getAuthHeaders(),
    }
  );
  return handleResponse<{
    league_id: string;
    team_id: string;
    team_name: string;
    players: any[];
    last_updated: string | null;
  }>(response);
}
