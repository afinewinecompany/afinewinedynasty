'use client';

import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api/client';

/**
 * Discovery parameters interface
 */
export interface DiscoveryParams {
  lookback_days: number;
  confidence_threshold: number;
  limit_per_category: number;
}

/**
 * Breakout candidate interface
 */
export interface BreakoutCandidate {
  prospect_id: number;
  mlb_id: string;
  name: string;
  position: string;
  organization: string | null;
  level: string | null;
  age: number | null;
  eta_year: number | null;
  breakout_score: number;
  improvement_metrics: {
    [key: string]: any;
  };
  statistical_significance: {
    is_significant: boolean;
    confidence_level: number;
  };
  recent_stats_summary: {
    [key: string]: any;
  };
  baseline_stats_summary: {
    [key: string]: any;
  };
  trend_indicators: {
    trend_consistency: number;
    max_improvement_rate: number;
    avg_improvement_rate: number;
    data_points: number;
  };
}

/**
 * Sleeper prospect interface
 */
export interface SleeperProspect {
  prospect_id: number;
  mlb_id: string;
  name: string;
  position: string;
  organization: string | null;
  level: string | null;
  age: number | null;
  eta_year: number | null;
  sleeper_score: number;
  ml_confidence: number;
  consensus_ranking_gap: number;
  undervaluation_factors: string[];
  ml_predictions: {
    [key: string]: any;
  };
  market_analysis: {
    ml_vs_consensus_gap: number;
    ml_confidence_level: number;
    market_inefficiency_score: number;
    opportunity_window: string;
    risk_factors: string[];
    upside_factors: string[];
  };
}

/**
 * Discovery metadata interface
 */
export interface DiscoveryMetadata {
  analysis_date: string;
  lookback_days: number;
  confidence_threshold: number;
  total_breakout_candidates: number;
  total_sleeper_prospects: number;
  avg_breakout_score: number;
  avg_sleeper_score: number;
}

/**
 * Hook for managing discovery dashboard data and operations
 *
 * Provides comprehensive discovery functionality including breakout candidates,
 * sleeper prospects, organizational insights, and position scarcity analysis.
 *
 * @param params Discovery parameters
 * @returns Discovery state and operations
 */
export function useDiscovery(params: DiscoveryParams) {
  // Fetch breakout candidates
  const {
    data: breakoutCandidates,
    isLoading: isLoadingBreakout,
    error: breakoutError,
    refetch: refetchBreakout,
  } = useQuery({
    queryKey: ['breakout-candidates', params],
    queryFn: async () => {
      const response = await api.get('/discovery/breakout-candidates', {
        params: {
          lookback_days: params.lookback_days,
          min_improvement_threshold: 0.1,
          limit: params.limit_per_category,
        },
      });
      return response.data as BreakoutCandidate[];
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 30 * 60 * 1000, // 30 minutes
  });

  // Fetch sleeper prospects
  const {
    data: sleeperProspects,
    isLoading: isLoadingSleeper,
    error: sleeperError,
    refetch: refetchSleeper,
  } = useQuery({
    queryKey: ['sleeper-prospects', params],
    queryFn: async () => {
      const response = await api.get('/discovery/sleeper-prospects', {
        params: {
          confidence_threshold: params.confidence_threshold,
          consensus_ranking_gap: 30,
          limit: params.limit_per_category,
        },
      });
      return response.data as SleeperProspect[];
    },
    staleTime: 5 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
  });

  // Fetch complete discovery dashboard
  const {
    data: dashboardData,
    isLoading: isLoadingDashboard,
    error: dashboardError,
    refetch: refetchDashboard,
  } = useQuery({
    queryKey: ['discovery-dashboard', params],
    queryFn: async () => {
      const response = await api.get('/discovery/dashboard', {
        params: {
          lookback_days: params.lookback_days,
          confidence_threshold: params.confidence_threshold,
          limit_per_category: params.limit_per_category,
        },
      });
      return response.data;
    },
    staleTime: 10 * 60 * 1000, // 10 minutes
    gcTime: 60 * 60 * 1000, // 1 hour
  });

  // Combined loading state
  const isLoading = isLoadingBreakout || isLoadingSleeper || isLoadingDashboard;

  // Combined error state
  const error = breakoutError || sleeperError || dashboardError;

  // Refetch all data
  const refetch = async () => {
    await Promise.all([
      refetchBreakout(),
      refetchSleeper(),
      refetchDashboard(),
    ]);
  };

  return {
    // Data
    breakoutCandidates,
    sleeperProspects,
    organizationalInsights: dashboardData?.organizational_insights,
    positionScarcity: dashboardData?.position_scarcity,
    discoveryMetadata: dashboardData?.discovery_metadata as DiscoveryMetadata,

    // State
    isLoading,
    error,

    // Actions
    refetch,

    // Individual refetch functions
    refetchBreakout,
    refetchSleeper,
    refetchDashboard,
  };
}

/**
 * Hook for breakout candidates only
 */
export function useBreakoutCandidates(
  lookbackDays: number = 30,
  improvementThreshold: number = 0.1,
  limit: number = 25
) {
  return useQuery({
    queryKey: [
      'breakout-candidates',
      lookbackDays,
      improvementThreshold,
      limit,
    ],
    queryFn: async () => {
      const response = await api.get('/discovery/breakout-candidates', {
        params: {
          lookback_days: lookbackDays,
          min_improvement_threshold: improvementThreshold,
          limit,
        },
      });
      return response.data as BreakoutCandidate[];
    },
    staleTime: 5 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
  });
}

/**
 * Hook for sleeper prospects only
 */
export function useSleeperProspects(
  confidenceThreshold: number = 0.7,
  consensusGap: number = 50,
  limit: number = 25
) {
  return useQuery({
    queryKey: ['sleeper-prospects', confidenceThreshold, consensusGap, limit],
    queryFn: async () => {
      const response = await api.get('/discovery/sleeper-prospects', {
        params: {
          confidence_threshold: confidenceThreshold,
          consensus_ranking_gap: consensusGap,
          limit,
        },
      });
      return response.data as SleeperProspect[];
    },
    staleTime: 5 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
  });
}
