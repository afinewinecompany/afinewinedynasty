export interface Prospect {
  id: string;
  mlb_id: string;
  name: string;
  position: string;
  organization: string;
  level: string;
  age: number;
  eta_year?: number;
}

export interface ProspectStats {
  prospect_id: string;
  timestamp: string;
  // Hitting stats
  games_played?: number;
  at_bats?: number;
  hits?: number;
  home_runs?: number;
  rbi?: number;
  batting_avg?: number;
  on_base_pct?: number;
  slugging_pct?: number;
  // Pitching stats
  innings_pitched?: number;
  era?: number;
  whip?: number;
  strikeouts_per_nine?: number;
  // Performance metrics
  woba?: number;
  wrc_plus?: number;
}

export interface MLPrediction {
  prospect_id: string;
  success_probability: number;
  confidence_level: 'High' | 'Medium' | 'Low';
  explanation?: string;
  generated_at: string;
}

export interface ProspectProfile extends Prospect {
  stats?: ProspectStats[];
  ml_prediction?: MLPrediction;
  scouting_grade?: number;
  dynasty_metrics?: {
    dynasty_score?: number;
    ml_score?: number;
    scouting_score?: number;
    confidence_level?: string;
  };
  scouting_grades?: {
    overall?: number;
    future_value?: number;
    hit?: number;
    power?: number;
    speed?: number;
    field?: number;
    arm?: number;
  };
}

export interface ProspectListParams {
  page?: number;
  limit?: number;
  position?: string;
  organization?: string;
  sort_by?: 'age' | 'level' | 'organization' | 'name';
  sort_order?: 'asc' | 'desc';
  search?: string;
}

export interface ProspectListResponse {
  prospects: Prospect[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}

// New interfaces for rankings dashboard
export interface ProspectRanking {
  id: number;
  mlbId: string;
  name: string;
  position: string;
  organization: string | null;
  level: string | null;
  age: number | null;
  etaYear: number | null;
  dynastyRank: number;
  dynastyScore: number;
  mlScore: number;
  scoutingScore: number;
  confidenceLevel: 'High' | 'Medium' | 'Low';
  battingAvg?: number | null;
  onBasePct?: number | null;
  sluggingPct?: number | null;
  era?: number | null;
  whip?: number | null;
  overallGrade?: number | null;
  futureValue?: number | null;
}

export interface ProspectRankingsResponse {
  prospects: ProspectRanking[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export interface ProspectRankingsParams {
  page?: number;
  pageSize?: number;
  limit?: number;
  position?: string[];
  organization?: string[];
  level?: string[];
  etaMin?: number;
  etaMax?: number;
  ageMin?: number;
  ageMax?: number;
  search?: string;
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
}

export interface ProspectSearchSuggestion {
  name: string;
  organization: string | null;
  position: string;
  display: string;
}

export interface ScoutingGrade {
  source:
    | 'Fangraphs'
    | 'MLB Pipeline'
    | 'Baseball America'
    | 'Baseball Prospectus';
  overall?: number;
  hit?: number;
  power?: number;
  run?: number;
  field?: number;
  throw?: number;
  fastball?: number;
  curveball?: number;
  slider?: number;
  changeup?: number;
  control?: number;
  futureValue?: number;
  risk?: 'Safe' | 'Moderate' | 'High' | 'Extreme';
  updatedAt: string;
}

// Comparison interfaces
export interface ComparisonProspect {
  id: string;
  name: string;
  position: string;
  organization: string;
  level?: string;
  age?: number;
  eta_year?: number;
  dynasty_metrics?: {
    dynasty_score?: number;
    ml_score?: number;
    scouting_score?: number;
    confidence_level?: string;
  };
  stats?: {
    batting_avg?: number;
    on_base_pct?: number;
    slugging_pct?: number;
    ops?: number;
    wrc_plus?: number;
    walk_rate?: number;
    strikeout_rate?: number;
    era?: number;
    whip?: number;
    k_per_9?: number;
    bb_per_9?: number;
    fip?: number;
  };
  scouting_grades?: {
    overall?: number;
    future_value?: number;
    hit?: number;
    power?: number;
    speed?: number;
    field?: number;
    arm?: number;
  };
  ml_prediction?: {
    success_probability?: number;
    confidence_level?: string;
  };
}

export interface ComparisonData {
  prospects: ComparisonProspect[];
  comparison_metadata: {
    generated_at: string;
  };
  statistical_comparison?: {
    performance_gaps?: Array<{
      leader: string;
      metric: string;
      percentage_gap: string;
      trailing_prospect: string;
    }>;
  };
}

// Composite Rankings (FanGraphs + MiLB Performance)
export interface CompositeRanking {
  rank: number;
  prospect_id: number;
  name: string;
  position: string;
  organization: string | null;
  age: number | null;
  level: string | null;

  // Score breakdown
  composite_score: number;
  base_fv: number;
  performance_modifier: number;
  trend_adjustment: number;
  age_adjustment: number;
  total_adjustment: number;

  // Tool grades (position-specific)
  tool_grades: {
    hit?: number | null;
    power?: number | null;
    speed?: number | null;
    field?: number | null;
    fastball?: number | null;
    slider?: number | null;
    curve?: number | null;
    change?: number | null;
    command?: number | null;
  };

  // Tier classification
  tier: number | null;
  tier_label: string | null;
}

export interface CompositeRankingsResponse {
  prospects: CompositeRanking[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  generated_at: string;
}

export interface CompositeRankingsParams {
  page?: number;
  page_size?: number;
  position?: string;
  organization?: string;
  limit?: number;
}
