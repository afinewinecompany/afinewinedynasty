/**
 * API client for recommendation endpoints
 *
 * Provides functions for fetching team needs, prospect recommendations,
 * trade targets, draft strategy, stash candidates, and user preferences.
 *
 * @module lib/api/recommendations
 * @since 1.0.0
 */

import { apiClient } from './client';
import type {
  TeamNeeds,
  ProspectRecommendationsQuery,
  ProspectRecommendationsResponse,
  TradeTargetsQuery,
  TradeTargetsResponse,
  DraftStrategyQuery,
  DraftStrategyResponse,
  StashCandidatesResponse,
  UserPreferences,
} from '@/types/recommendations';

/**
 * Get team needs analysis for a league
 *
 * @param leagueId - Fantrax league ID
 * @returns Team needs analysis
 *
 * @example
 * ```typescript
 * const teamNeeds = await getTeamNeeds('abc123');
 * console.log(teamNeeds.competitive_window); // 'contending'
 * ```
 *
 * @since 1.0.0
 */
export async function getTeamNeeds(leagueId: string): Promise<TeamNeeds> {
  return apiClient.get<TeamNeeds>(
    `/api/recommendations/team-needs/${leagueId}`,
    60 // Cache for 1 hour
  );
}

/**
 * Get prospect recommendations for a league
 *
 * @param leagueId - Fantrax league ID
 * @param query - Query parameters (limit, risk_tolerance)
 * @returns Prospect recommendations
 *
 * @example
 * ```typescript
 * const recommendations = await getProspectRecommendations('abc123', {
 *   limit: 20,
 *   risk_tolerance: 'balanced'
 * });
 * ```
 *
 * @since 1.0.0
 */
export async function getProspectRecommendations(
  leagueId: string,
  query?: ProspectRecommendationsQuery
): Promise<ProspectRecommendationsResponse> {
  const params = new URLSearchParams();
  if (query?.limit) params.append('limit', query.limit.toString());
  if (query?.risk_tolerance)
    params.append('risk_tolerance', query.risk_tolerance);

  const queryString = params.toString();
  const endpoint = `/api/recommendations/prospects/${leagueId}${queryString ? `?${queryString}` : ''}`;

  return apiClient.get<ProspectRecommendationsResponse>(
    endpoint,
    30 // Cache for 30 minutes
  );
}

/**
 * Get trade targets for a league
 *
 * @param leagueId - Fantrax league ID
 * @param query - Query parameters (category filter)
 * @returns Trade targets (buy-low, sell-high, arbitrage)
 *
 * @example
 * ```typescript
 * const targets = await getTradeTargets('abc123', {
 *   category: 'buy_low'
 * });
 * ```
 *
 * @since 1.0.0
 */
export async function getTradeTargets(
  leagueId: string,
  query?: TradeTargetsQuery
): Promise<TradeTargetsResponse> {
  const params = new URLSearchParams();
  if (query?.category) params.append('category', query.category);

  const queryString = params.toString();
  const endpoint = `/api/recommendations/trade-targets/${leagueId}${queryString ? `?${queryString}` : ''}`;

  return apiClient.get<TradeTargetsResponse>(
    endpoint,
    30 // Cache for 30 minutes
  );
}

/**
 * Get draft strategy recommendations for a league
 *
 * @param leagueId - Fantrax league ID
 * @param query - Query parameters (pick_number)
 * @returns Draft strategy with tiered recommendations
 *
 * @example
 * ```typescript
 * const strategy = await getDraftStrategy('abc123', {
 *   pick_number: 5
 * });
 * ```
 *
 * @since 1.0.0
 */
export async function getDraftStrategy(
  leagueId: string,
  query?: DraftStrategyQuery
): Promise<DraftStrategyResponse> {
  const params = new URLSearchParams();
  if (query?.pick_number)
    params.append('pick_number', query.pick_number.toString());

  const queryString = params.toString();
  const endpoint = `/api/recommendations/draft-strategy/${leagueId}${queryString ? `?${queryString}` : ''}`;

  return apiClient.get<DraftStrategyResponse>(
    endpoint,
    30 // Cache for 30 minutes
  );
}

/**
 * Get stash candidates for a league
 *
 * @param leagueId - Fantrax league ID
 * @returns Stash candidates with upside scores
 *
 * @example
 * ```typescript
 * const stashCandidates = await getStashCandidates('abc123');
 * console.log(stashCandidates.available_spots); // 3
 * ```
 *
 * @since 1.0.0
 */
export async function getStashCandidates(
  leagueId: string
): Promise<StashCandidatesResponse> {
  return apiClient.get<StashCandidatesResponse>(
    `/api/recommendations/stash-candidates/${leagueId}`,
    30 // Cache for 30 minutes
  );
}

/**
 * Get user's recommendation preferences
 *
 * @returns User preferences
 *
 * @example
 * ```typescript
 * const preferences = await getUserPreferences();
 * console.log(preferences.risk_tolerance); // 'balanced'
 * ```
 *
 * @since 1.0.0
 */
export async function getUserPreferences(): Promise<UserPreferences> {
  return apiClient.get<UserPreferences>('/api/recommendations/preferences');
}

/**
 * Update user's recommendation preferences
 *
 * @param preferences - Updated preferences
 * @returns Updated preferences
 *
 * @example
 * ```typescript
 * const updated = await updateUserPreferences({
 *   risk_tolerance: 'aggressive',
 *   prefer_win_now: true,
 *   prefer_rebuild: false,
 *   position_priorities: ['SP', 'OF'],
 *   prefer_buy_low: true,
 *   prefer_sell_high: false
 * });
 * ```
 *
 * @since 1.0.0
 */
export async function updateUserPreferences(
  preferences: UserPreferences
): Promise<UserPreferences> {
  return apiClient.put<UserPreferences>(
    '/api/recommendations/preferences',
    preferences
  );
}
