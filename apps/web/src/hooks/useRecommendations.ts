/**
 * Custom React hook for recommendation data management
 *
 * Provides state management and operations for fetching team needs,
 * prospect recommendations, trade targets, draft strategy, stash candidates,
 * and user preferences.
 *
 * @module hooks/useRecommendations
 * @since 1.0.0
 */

import { useState, useCallback } from 'react';
import type {
  TeamNeeds,
  ProspectRecommendationsQuery,
  RecommendationDetails,
  TradeTargetsQuery,
  TradeTargetsResponse,
  DraftStrategyQuery,
  DraftStrategyResponse,
  StashCandidatesResponse,
  UserPreferences,
} from '@/types/recommendations';
import * as recommendationsApi from '@/lib/api/recommendations';

/**
 * Hook state interface
 */
interface UseRecommendationsState {
  /** Team needs analysis data */
  teamNeeds: TeamNeeds | null;
  /** Prospect recommendations */
  prospectRecommendations: RecommendationDetails[];
  /** Trade targets data */
  tradeTargets: TradeTargetsResponse | null;
  /** Draft strategy data */
  draftStrategy: DraftStrategyResponse | null;
  /** Stash candidates data */
  stashCandidates: StashCandidatesResponse | null;
  /** User preferences */
  preferences: UserPreferences | null;
  /** Loading states */
  loading: {
    teamNeeds: boolean;
    prospects: boolean;
    tradeTargets: boolean;
    draftStrategy: boolean;
    stashCandidates: boolean;
    preferences: boolean;
  };
  /** Error states */
  error: {
    teamNeeds: string | null;
    prospects: string | null;
    tradeTargets: string | null;
    draftStrategy: string | null;
    stashCandidates: string | null;
    preferences: string | null;
  };
}

/**
 * Hook return interface
 */
interface UseRecommendationsReturn extends UseRecommendationsState {
  /** Fetch team needs analysis */
  fetchTeamNeeds: (leagueId: string) => Promise<void>;
  /** Fetch prospect recommendations */
  fetchProspectRecommendations: (
    leagueId: string,
    query?: ProspectRecommendationsQuery
  ) => Promise<void>;
  /** Fetch trade targets */
  fetchTradeTargets: (
    leagueId: string,
    query?: TradeTargetsQuery
  ) => Promise<void>;
  /** Fetch draft strategy */
  fetchDraftStrategy: (
    leagueId: string,
    query?: DraftStrategyQuery
  ) => Promise<void>;
  /** Fetch stash candidates */
  fetchStashCandidates: (leagueId: string) => Promise<void>;
  /** Fetch user preferences */
  fetchPreferences: () => Promise<void>;
  /** Update user preferences */
  updatePreferences: (preferences: UserPreferences) => Promise<void>;
  /** Clear all data */
  clearAll: () => void;
}

/**
 * Custom hook for managing recommendation data
 *
 * @returns Recommendation state and operations
 *
 * @example
 * ```typescript
 * function MyComponent() {
 *   const {
 *     teamNeeds,
 *     prospectRecommendations,
 *     loading,
 *     error,
 *     fetchTeamNeeds,
 *     fetchProspectRecommendations,
 *   } = useRecommendations();
 *
 *   useEffect(() => {
 *     if (leagueId) {
 *       fetchTeamNeeds(leagueId);
 *       fetchProspectRecommendations(leagueId, { limit: 20 });
 *     }
 *   }, [leagueId]);
 *
 *   return <div>...</div>;
 * }
 * ```
 *
 * @since 1.0.0
 */
export function useRecommendations(): UseRecommendationsReturn {
  const [state, setState] = useState<UseRecommendationsState>({
    teamNeeds: null,
    prospectRecommendations: [],
    tradeTargets: null,
    draftStrategy: null,
    stashCandidates: null,
    preferences: null,
    loading: {
      teamNeeds: false,
      prospects: false,
      tradeTargets: false,
      draftStrategy: false,
      stashCandidates: false,
      preferences: false,
    },
    error: {
      teamNeeds: null,
      prospects: null,
      tradeTargets: null,
      draftStrategy: null,
      stashCandidates: null,
      preferences: null,
    },
  });

  /**
   * Update loading state for a specific operation
   */
  const setLoading = useCallback(
    (key: keyof UseRecommendationsState['loading'], value: boolean) => {
      setState((prev) => ({
        ...prev,
        loading: { ...prev.loading, [key]: value },
      }));
    },
    []
  );

  /**
   * Update error state for a specific operation
   */
  const setError = useCallback(
    (key: keyof UseRecommendationsState['error'], value: string | null) => {
      setState((prev) => ({
        ...prev,
        error: { ...prev.error, [key]: value },
      }));
    },
    []
  );

  /**
   * Fetch team needs analysis
   */
  const fetchTeamNeeds = useCallback(
    async (leagueId: string) => {
      setLoading('teamNeeds', true);
      setError('teamNeeds', null);

      try {
        const teamNeeds = await recommendationsApi.getTeamNeeds(leagueId);
        setState((prev) => ({ ...prev, teamNeeds }));
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'Failed to load team needs';
        setError('teamNeeds', message);
      } finally {
        setLoading('teamNeeds', false);
      }
    },
    [setLoading, setError]
  );

  /**
   * Fetch prospect recommendations
   */
  const fetchProspectRecommendations = useCallback(
    async (leagueId: string, query?: ProspectRecommendationsQuery) => {
      setLoading('prospects', true);
      setError('prospects', null);

      try {
        const response = await recommendationsApi.getProspectRecommendations(
          leagueId,
          query
        );
        setState((prev) => ({
          ...prev,
          prospectRecommendations: response.recommendations,
        }));
      } catch (err) {
        const message =
          err instanceof Error
            ? err.message
            : 'Failed to load prospect recommendations';
        setError('prospects', message);
      } finally {
        setLoading('prospects', false);
      }
    },
    [setLoading, setError]
  );

  /**
   * Fetch trade targets
   */
  const fetchTradeTargets = useCallback(
    async (leagueId: string, query?: TradeTargetsQuery) => {
      setLoading('tradeTargets', true);
      setError('tradeTargets', null);

      try {
        const tradeTargets = await recommendationsApi.getTradeTargets(
          leagueId,
          query
        );
        setState((prev) => ({ ...prev, tradeTargets }));
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'Failed to load trade targets';
        setError('tradeTargets', message);
      } finally {
        setLoading('tradeTargets', false);
      }
    },
    [setLoading, setError]
  );

  /**
   * Fetch draft strategy
   */
  const fetchDraftStrategy = useCallback(
    async (leagueId: string, query?: DraftStrategyQuery) => {
      setLoading('draftStrategy', true);
      setError('draftStrategy', null);

      try {
        const draftStrategy = await recommendationsApi.getDraftStrategy(
          leagueId,
          query
        );
        setState((prev) => ({ ...prev, draftStrategy }));
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'Failed to load draft strategy';
        setError('draftStrategy', message);
      } finally {
        setLoading('draftStrategy', false);
      }
    },
    [setLoading, setError]
  );

  /**
   * Fetch stash candidates
   */
  const fetchStashCandidates = useCallback(
    async (leagueId: string) => {
      setLoading('stashCandidates', true);
      setError('stashCandidates', null);

      try {
        const stashCandidates =
          await recommendationsApi.getStashCandidates(leagueId);
        setState((prev) => ({ ...prev, stashCandidates }));
      } catch (err) {
        const message =
          err instanceof Error
            ? err.message
            : 'Failed to load stash candidates';
        setError('stashCandidates', message);
      } finally {
        setLoading('stashCandidates', false);
      }
    },
    [setLoading, setError]
  );

  /**
   * Fetch user preferences
   */
  const fetchPreferences = useCallback(async () => {
    setLoading('preferences', true);
    setError('preferences', null);

    try {
      const preferences = await recommendationsApi.getUserPreferences();
      setState((prev) => ({ ...prev, preferences }));
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to load preferences';
      setError('preferences', message);
    } finally {
      setLoading('preferences', false);
    }
  }, [setLoading, setError]);

  /**
   * Update user preferences
   */
  const updatePreferences = useCallback(
    async (preferences: UserPreferences) => {
      setLoading('preferences', true);
      setError('preferences', null);

      try {
        const updated =
          await recommendationsApi.updateUserPreferences(preferences);
        setState((prev) => ({ ...prev, preferences: updated }));
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'Failed to update preferences';
        setError('preferences', message);
        throw err; // Re-throw to allow component to handle
      } finally {
        setLoading('preferences', false);
      }
    },
    [setLoading, setError]
  );

  /**
   * Clear all data
   */
  const clearAll = useCallback(() => {
    setState({
      teamNeeds: null,
      prospectRecommendations: [],
      tradeTargets: null,
      draftStrategy: null,
      stashCandidates: null,
      preferences: null,
      loading: {
        teamNeeds: false,
        prospects: false,
        tradeTargets: false,
        draftStrategy: false,
        stashCandidates: false,
        preferences: false,
      },
      error: {
        teamNeeds: null,
        prospects: null,
        tradeTargets: null,
        draftStrategy: null,
        stashCandidates: null,
        preferences: null,
      },
    });
  }, []);

  return {
    ...state,
    fetchTeamNeeds,
    fetchProspectRecommendations,
    fetchTradeTargets,
    fetchDraftStrategy,
    fetchStashCandidates,
    fetchPreferences,
    updatePreferences,
    clearAll,
  };
}
