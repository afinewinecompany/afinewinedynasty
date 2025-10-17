/**
 * TypeScript types for Fantrax integration
 *
 * Defines types for Fantrax leagues, rosters, recommendations,
 * and API request/response models.
 *
 * @module types/fantrax
 * @since 1.0.0
 */

/**
 * Fantrax league information
 */
export interface FantraxLeague {
  /** Unique Fantrax league ID */
  league_id: string;
  /** League name */
  league_name: string;
  /** League type */
  league_type?: 'dynasty' | 'keeper' | 'redraft';
  /** Sport (e.g., MLB, NFL) */
  sport?: string;
  /** Season year */
  season?: number;
  /** Number of teams in league */
  team_count: number;
  /** User's team ID in this league */
  my_team_id?: string;
  /** User's team name in this league */
  my_team_name?: string;
  /** Total roster size */
  roster_size: number;
  /** Scoring system type */
  scoring_type: string;
  /** Whether league is currently active */
  is_active: boolean;
  /** Last roster sync timestamp */
  last_sync?: string;
}

/**
 * Roster player information
 */
export interface RosterPlayer {
  /** Fantrax player ID */
  player_id: string;
  /** Player name */
  player_name: string;
  /** Eligible positions */
  positions: string[];
  /** MLB team */
  team: string;
  /** Player status */
  status: 'active' | 'injured' | 'minors' | 'suspended' | 'il';
  /** Contract years remaining */
  contract_years?: number;
  /** Contract value */
  contract_value?: number;
  /** Player age */
  age?: number;
  /** Whether player is minor league eligible */
  minor_league_eligible: boolean;
  /** When player was synced */
  synced_at: string;
}

/**
 * Roster data for a league
 */
export interface RosterData {
  /** League ID */
  league_id: string;
  /** Team ID in the league */
  team_id: string;
  /** Team name */
  team_name: string;
  /** List of players on roster */
  players: RosterPlayer[];
  /** Last update timestamp */
  last_updated: string;
}

/**
 * Team needs analysis result
 */
export interface TeamAnalysis {
  /** League ID analyzed */
  league_id: string;
  /** Strong positions */
  strengths: string[];
  /** Weak positions */
  weaknesses: string[];
  /** Projected future roster holes */
  future_holes: FutureHole[];
  /** Team competitive timeline */
  roster_timeline:
    | 'rebuilding'
    | 'emerging'
    | 'balanced'
    | 'competing'
    | 'win-now'
    | 'retooling';
  /** Available roster spots */
  available_spots: number;
  /** Number of matching prospects */
  recommendations_count: number;
  /** Position-by-position depth */
  position_depth: Record<string, PositionDepth>;
  /** Age curve analysis */
  age_analysis: AgeAnalysis;
  /** When analysis was generated */
  analysis_timestamp: string;
}

/**
 * Future roster hole projection
 */
export interface FutureHole {
  /** Position with projected hole */
  position: string;
  /** Year when hole will occur */
  year: number;
  /** Severity of the hole */
  severity: 'high' | 'medium' | 'low';
  /** Reason for the hole */
  reason: string;
  /** Affected players */
  affected_players: string[];
}

/**
 * Position depth analysis
 */
export interface PositionDepth {
  /** Current player count */
  current: number;
  /** Required player count */
  required: number;
  /** Surplus/deficit */
  surplus: number;
  /** Depth rating */
  rating: 'excellent' | 'good' | 'adequate' | 'poor' | 'critical';
}

/**
 * Age curve analysis
 */
export interface AgeAnalysis {
  /** Average age */
  avg_age: number;
  /** Median age */
  median_age: number;
  /** Count of young players */
  young_players: number;
  /** Count of prime age players */
  prime_players: number;
  /** Count of aging players */
  aging_players: number;
  /** Age distribution map */
  age_distribution: Record<number, number>;
  /** Overall age score (0-100) */
  age_score: number;
}

/**
 * Prospect recommendation
 */
export interface ProspectRecommendation {
  /** Prospect database ID */
  prospect_id: number;
  /** Prospect name */
  name: string;
  /** Primary position */
  position: string;
  /** MLB organization */
  organization: string;
  /** Expected MLB arrival year */
  eta_year: number;
  /** How well prospect fits team needs (0-100) */
  fit_score: number;
  /** Why this prospect is recommended */
  reason: string;
  /** Trade value tier */
  trade_value: string;
  /** Prospect age */
  age?: number;
}

/**
 * OAuth authorization response
 */
export interface OAuthAuthResponse {
  /** OAuth authorization URL */
  authorization_url: string;
  /** State token for CSRF protection */
  state: string;
}

/**
 * OAuth callback response
 */
export interface OAuthCallbackResponse {
  /** Whether connection was successful */
  success: boolean;
  /** Status message */
  message: string;
  /** Connected Fantrax user ID */
  fantrax_user_id?: string;
}

/**
 * Roster sync request
 */
export interface RosterSyncRequest {
  /** League ID to sync */
  league_id: string;
  /** Force refresh even if cached */
  force_refresh?: boolean;
}

/**
 * Roster sync response
 */
export interface RosterSyncResponse {
  /** Whether sync was successful */
  success: boolean;
  /** Number of players synced */
  players_synced: number;
  /** Timestamp of sync */
  sync_time: string;
  /** Status message */
  message: string;
}

/**
 * Trade analysis request
 */
export interface TradeAnalysisRequest {
  /** League ID for context */
  league_id: string;
  /** Players being acquired */
  acquiring: TradePlayer[];
  /** Players being given up */
  giving: TradePlayer[];
}

/**
 * Player in trade analysis
 */
export interface TradePlayer {
  /** Player ID */
  id: string;
  /** Player type */
  type: 'prospect' | 'mlb';
  /** Player name */
  name: string;
  /** Player position */
  position: string;
  /** Player value (for MLB players) */
  value?: number;
}

/**
 * Trade analysis response
 */
export interface TradeAnalysisResponse {
  /** Total value of players acquired */
  acquiring_value: number;
  /** Total value of players given up */
  giving_value: number;
  /** Net value change */
  value_difference: number;
  /** How trade improves team fit */
  fit_improvement: number;
  /** Trade recommendation */
  recommendation: string;
  /** Confidence level */
  confidence: 'high' | 'medium' | 'low';
  /** Detailed analysis */
  analysis: {
    /** Timeline match assessment */
    timeline_match: string;
    /** Whether needs are addressed */
    need_addressed: boolean;
    /** Roster impact assessment */
    roster_impact: string;
  };
}

/**
 * Connection status
 */
export interface ConnectionStatus {
  /** Whether Fantrax is connected */
  connected: boolean;
  /** Connected Fantrax user ID */
  fantrax_user_id?: string;
  /** When connection was established */
  connected_at?: string;
  /** Number of leagues found */
  leagues_count?: number;
}

/**
 * Error response from API
 */
export interface FantraxError {
  /** Error message */
  detail: string;
  /** Error code */
  code?: string;
}
