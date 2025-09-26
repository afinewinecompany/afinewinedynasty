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
  source: 'Fangraphs' | 'MLB Pipeline' | 'Baseball America' | 'Baseball Prospectus';
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
