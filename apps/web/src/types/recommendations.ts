/**
 * TypeScript types for recommendation system
 *
 * Defines types for team needs analysis, prospect recommendations,
 * trade targets, draft strategy, stash candidates, and user preferences.
 *
 * @module types/recommendations
 * @since 1.0.0
 */

/**
 * Positional need with severity and timeline
 */
export interface PositionalNeed {
  /** Position requiring attention */
  position: string;
  /** Severity level of the need */
  severity: 'critical' | 'high' | 'medium' | 'low';
  /** Timeline for addressing the need */
  timeline: 'immediate' | 'near_term' | 'long_term';
}

/**
 * Depth analysis for a single position
 */
export interface DepthAnalysis {
  /** Number of starting-quality players */
  starters: number;
  /** Number of depth/backup players */
  depth: number;
  /** Gap score indicating shortage (0-100) */
  gap_score: number;
}

/**
 * Future needs projection by year
 */
export interface FutureNeeds {
  /** Positions needed in 2 years */
  '2_year': string[];
  /** Positions needed in 3 years */
  '3_year': string[];
}

/**
 * Team needs analysis response
 */
export interface TeamNeeds {
  /** List of positional needs with severity */
  positional_needs: PositionalNeed[];
  /** Position-by-position depth analysis */
  depth_analysis: Record<string, DepthAnalysis>;
  /** Team's competitive window classification */
  competitive_window: 'contending' | 'transitional' | 'rebuilding';
  /** Future roster needs projections */
  future_needs: FutureNeeds;
}

/**
 * Detailed prospect recommendation with fit breakdown
 */
export interface RecommendationDetails {
  /** Prospect database ID */
  prospect_id: number;
  /** Overall fit score (0-100) */
  fit_score: number;
  /** How well position matches team needs (0-100) */
  position_fit: number;
  /** How well ETA matches competitive timeline (0-100) */
  timeline_fit: number;
  /** Trade value tier */
  value_rating: 'elite' | 'high' | 'medium' | 'low' | 'speculative';
  /** Explanation of why prospect is recommended */
  explanation: string;
  /** Confidence level in recommendation */
  confidence: 'high' | 'medium' | 'low';
}

/**
 * Query parameters for prospect recommendations
 */
export interface ProspectRecommendationsQuery {
  /** Maximum number of recommendations to return */
  limit?: number;
  /** User's risk tolerance preference */
  risk_tolerance?: 'conservative' | 'balanced' | 'aggressive';
}

/**
 * Prospect recommendations response
 */
export interface ProspectRecommendationsResponse {
  /** List of recommended prospects */
  recommendations: RecommendationDetails[];
}

/**
 * Trade target candidate
 */
export interface TradeTargetCandidate {
  /** Prospect database ID */
  prospect_id: number;
  /** Prospect name */
  name: string;
  /** Primary position */
  position: string;
  /** Current trade value assessment */
  current_value: string;
  /** Target value tier */
  target_value: string;
  /** Reasoning for recommendation */
  reasoning: string;
  /** Opportunity type */
  opportunity_type: 'buy_low' | 'sell_high' | 'arbitrage';
}

/**
 * Trade targets query parameters
 */
export interface TradeTargetsQuery {
  /** Filter by opportunity category */
  category?: 'buy_low' | 'sell_high' | 'arbitrage';
}

/**
 * Trade targets response
 */
export interface TradeTargetsResponse {
  /** Undervalued prospects to acquire */
  buy_low_candidates: TradeTargetCandidate[];
  /** Overvalued prospects to sell */
  sell_high_opportunities: TradeTargetCandidate[];
  /** Value arbitrage opportunities */
  trade_value_arbitrage: TradeTargetCandidate[];
}

/**
 * Draft prospect recommendation
 */
export interface DraftProspectRecommendation {
  /** Prospect database ID */
  prospect_id: number;
  /** Prospect name */
  name: string;
  /** Primary position */
  position: string;
  /** Draft value tier */
  draft_value: string;
  /** How well prospect matches team needs */
  need_match: number;
}

/**
 * Draft strategy query parameters
 */
export interface DraftStrategyQuery {
  /** Current pick number for context */
  pick_number?: number;
}

/**
 * Draft strategy response
 */
export interface DraftStrategyResponse {
  /** Top-tier draft targets */
  tier_1: DraftProspectRecommendation[];
  /** Second-tier draft targets */
  tier_2: DraftProspectRecommendation[];
  /** Third-tier draft targets */
  tier_3?: DraftProspectRecommendation[];
  /** Best player available vs need recommendation */
  bpa_vs_need: string;
  /** Deep sleeper prospects */
  sleepers: DraftProspectRecommendation[];
}

/**
 * Stash candidate recommendation
 */
export interface StashCandidate {
  /** Prospect database ID */
  prospect_id: number;
  /** Prospect name */
  name: string;
  /** Primary position */
  position: string;
  /** Upside potential score (0-100) */
  upside_score: number;
  /** Expected MLB arrival year */
  eta: number;
  /** Reasoning for stashing */
  reasoning: string;
}

/**
 * Stash candidates response
 */
export interface StashCandidatesResponse {
  /** Number of available roster spots */
  available_spots: number;
  /** List of stash candidate prospects */
  stash_candidates: StashCandidate[];
}

/**
 * User recommendation preferences
 */
export interface UserPreferences {
  /** Risk tolerance level */
  risk_tolerance: 'conservative' | 'balanced' | 'aggressive';
  /** Prefer win-now prospects */
  prefer_win_now: boolean;
  /** Prefer rebuild prospects */
  prefer_rebuild: boolean;
  /** Prioritized positions */
  position_priorities: string[];
  /** Prefer buy-low opportunities */
  prefer_buy_low: boolean;
  /** Prefer sell-high opportunities */
  prefer_sell_high: boolean;
}

/**
 * Recommendation filter options
 */
export interface RecommendationFilters {
  /** Filter by risk tolerance */
  risk_tolerance?: 'conservative' | 'balanced' | 'aggressive';
  /** Filter by positions */
  positions?: string[];
  /** Filter by ETA year range */
  eta_min?: number;
  eta_max?: number;
  /** Filter by trade value */
  trade_values?: string[];
}
