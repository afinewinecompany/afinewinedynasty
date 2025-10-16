/**
 * Custom React hook for Fantrax integration
 *
 * Provides state management and operations for Fantrax league integration
 * including OAuth, roster sync, and recommendations.
 *
 * @module hooks/useFantrax
 * @since 1.0.0
 */

import { useState, useCallback, useEffect } from 'react';
import type {
  FantraxLeague,
  RosterData,
  TeamAnalysis,
  ProspectRecommendation,
  ConnectionStatus,
} from '@/types/fantrax';
import * as fantraxApi from '@/lib/api/fantrax';

/**
 * Hook state interface
 */
interface UseFantraxState {
  /** Whether user is connected to Fantrax */
  isConnected: boolean;
  /** User's Fantrax leagues */
  leagues: FantraxLeague[];
  /** Currently selected league */
  selectedLeague: FantraxLeague | null;
  /** Current roster data */
  roster: RosterData | null;
  /** Team analysis results */
  analysis: TeamAnalysis | null;
  /** Prospect recommendations */
  recommendations: ProspectRecommendation[];
  /** Loading states */
  loading: {
    connection: boolean;
    leagues: boolean;
    roster: boolean;
    analysis: boolean;
    recommendations: boolean;
    sync: boolean;
  };
  /** Error states */
  error: {
    connection: string | null;
    leagues: string | null;
    roster: string | null;
    analysis: string | null;
    recommendations: string | null;
    sync: string | null;
  };
}

/**
 * Hook return interface
 */
interface UseFantraxReturn extends UseFantraxState {
  /** Connect to Fantrax (initiates OAuth flow) */
  connect: () => Promise<void>;
  /** Disconnect from Fantrax */
  disconnect: () => Promise<void>;
  /** Refresh leagues list */
  refreshLeagues: () => Promise<void>;
  /** Select a league */
  selectLeague: (league: FantraxLeague) => void;
  /** Sync roster for selected league */
  syncRoster: (forceRefresh?: boolean) => Promise<void>;
  /** Load team analysis */
  loadAnalysis: () => Promise<void>;
  /** Load recommendations */
  loadRecommendations: (limit?: number) => Promise<void>;
  /** Check connection status */
  checkConnection: () => Promise<void>;
}

/**
 * Custom hook for managing Fantrax integration
 *
 * @returns Fantrax state and operations
 *
 * @example
 * ```typescript
 * function MyComponent() {
 *   const {
 *     isConnected,
 *     leagues,
 *     selectedLeague,
 *     connect,
 *     selectLeague,
 *     syncRoster,
 *   } = useFantrax();
 *
 *   if (!isConnected) {
 *     return <button onClick={connect}>Connect Fantrax</button>;
 *   }
 *
 *   return (
 *     <div>
 *       {leagues.map(league => (
 *         <button key={league.league_id} onClick={() => selectLeague(league)}>
 *           {league.league_name}
 *         </button>
 *       ))}
 *     </div>
 *   );
 * }
 * ```
 *
 * @since 1.0.0
 */
export function useFantrax(): UseFantraxReturn {
  const [state, setState] = useState<UseFantraxState>({
    isConnected: false,
    leagues: [],
    selectedLeague: null,
    roster: null,
    analysis: null,
    recommendations: [],
    loading: {
      connection: false,
      leagues: false,
      roster: false,
      analysis: false,
      recommendations: false,
      sync: false,
    },
    error: {
      connection: null,
      leagues: null,
      roster: null,
      analysis: null,
      recommendations: null,
      sync: null,
    },
  });

  /**
   * Update loading state for a specific operation
   */
  const setLoading = useCallback(
    (key: keyof UseFantraxState['loading'], value: boolean) => {
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
    (key: keyof UseFantraxState['error'], value: string | null) => {
      setState((prev) => ({
        ...prev,
        error: { ...prev.error, [key]: value },
      }));
    },
    []
  );

  /**
   * Check Fantrax connection status
   */
  const checkConnection = useCallback(async () => {
    setLoading('connection', true);
    setError('connection', null);

    try {
      const status = await fantraxApi.getConnectionStatus();
      setState((prev) => ({
        ...prev,
        isConnected: status.connected,
      }));
    } catch (err) {
      // Silently set as not connected - this is expected if user hasn't connected yet
      // Don't show error message for initial connection check
      setState((prev) => ({ ...prev, isConnected: false }));
    } finally {
      setLoading('connection', false);
    }
  }, [setLoading, setError]);

  /**
   * Connect to Fantrax (initiate OAuth flow)
   */
  const connect = useCallback(async () => {
    setLoading('connection', true);
    setError('connection', null);

    try {
      const { authorization_url } = await fantraxApi.getAuthorizationUrl();
      // Redirect to Fantrax OAuth page
      window.location.href = authorization_url;
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to initiate connection';
      setError('connection', message);
      setLoading('connection', false);
    }
  }, [setLoading, setError]);

  /**
   * Disconnect from Fantrax
   */
  const disconnect = useCallback(async () => {
    setLoading('connection', true);
    setError('connection', null);

    try {
      await fantraxApi.disconnectFantrax();
      setState({
        isConnected: false,
        leagues: [],
        selectedLeague: null,
        roster: null,
        analysis: null,
        recommendations: [],
        loading: {
          connection: false,
          leagues: false,
          roster: false,
          analysis: false,
          recommendations: false,
          sync: false,
        },
        error: {
          connection: null,
          leagues: null,
          roster: null,
          analysis: null,
          recommendations: null,
          sync: null,
        },
      });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to disconnect';
      setError('connection', message);
    } finally {
      setLoading('connection', false);
    }
  }, [setLoading, setError]);

  /**
   * Refresh leagues list
   */
  const refreshLeagues = useCallback(async () => {
    setLoading('leagues', true);
    setError('leagues', null);

    try {
      const leagues = await fantraxApi.getUserLeagues();
      setState((prev) => ({
        ...prev,
        leagues,
        isConnected: true,
      }));
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to load leagues';
      setError('leagues', message);
    } finally {
      setLoading('leagues', false);
    }
  }, [setLoading, setError]);

  /**
   * Select a league
   */
  const selectLeague = useCallback((league: FantraxLeague) => {
    setState((prev) => ({
      ...prev,
      selectedLeague: league,
      // Clear previous league data
      roster: null,
      analysis: null,
      recommendations: [],
    }));
  }, []);

  /**
   * Sync roster for selected league
   */
  const syncRoster = useCallback(
    async (forceRefresh: boolean = false) => {
      if (!state.selectedLeague) {
        setError('sync', 'No league selected');
        return;
      }

      setLoading('sync', true);
      setError('sync', null);

      try {
        await fantraxApi.syncRoster({
          league_id: state.selectedLeague.league_id,
          force_refresh: forceRefresh,
        });

        // Load the roster data after sync
        setLoading('roster', true);
        const roster = await fantraxApi.getRoster(
          state.selectedLeague.league_id
        );
        setState((prev) => ({ ...prev, roster }));
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'Failed to sync roster';
        setError('sync', message);
      } finally {
        setLoading('sync', false);
        setLoading('roster', false);
      }
    },
    [state.selectedLeague, setLoading, setError]
  );

  /**
   * Load team analysis
   */
  const loadAnalysis = useCallback(async () => {
    if (!state.selectedLeague) {
      setError('analysis', 'No league selected');
      return;
    }

    setLoading('analysis', true);
    setError('analysis', null);

    try {
      const analysis = await fantraxApi.getTeamAnalysis(
        state.selectedLeague.league_id
      );
      setState((prev) => ({ ...prev, analysis }));
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to load analysis';
      setError('analysis', message);
    } finally {
      setLoading('analysis', false);
    }
  }, [state.selectedLeague, setLoading, setError]);

  /**
   * Load recommendations
   */
  const loadRecommendations = useCallback(
    async (limit: number = 10) => {
      if (!state.selectedLeague) {
        setError('recommendations', 'No league selected');
        return;
      }

      setLoading('recommendations', true);
      setError('recommendations', null);

      try {
        const recommendations = await fantraxApi.getRecommendations(
          state.selectedLeague.league_id,
          limit
        );
        setState((prev) => ({ ...prev, recommendations }));
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'Failed to load recommendations';
        setError('recommendations', message);
      } finally {
        setLoading('recommendations', false);
      }
    },
    [state.selectedLeague, setLoading, setError]
  );

  // Check connection on mount
  useEffect(() => {
    checkConnection();
  }, [checkConnection]);

  // Load leagues when connected
  useEffect(() => {
    if (state.isConnected && state.leagues.length === 0) {
      refreshLeagues();
    }
  }, [state.isConnected, state.leagues.length, refreshLeagues]);

  return {
    ...state,
    connect,
    disconnect,
    refreshLeagues,
    selectLeague,
    syncRoster,
    loadAnalysis,
    loadRecommendations,
    checkConnection,
  };
}
