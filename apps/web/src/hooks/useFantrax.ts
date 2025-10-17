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
      await fantraxApi.disconnectSecretAPI();
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
      const secretAPILeagues = await fantraxApi.getSecretAPILeagues();
      // Convert Secret API league format to existing FantraxLeague format
      const leagues: FantraxLeague[] = secretAPILeagues.map((league) => ({
        league_id: league.league_id,
        league_name: league.name,
        sport: league.sport || 'MLB',
        team_count: league.teams?.length || 0,
        // Use my_team_id from API response (from database or manually selected)
        my_team_id: league.my_team_id || league.teams?.[0]?.team_id,
        my_team_name: league.my_team_name || league.teams?.[0]?.team_name,
        roster_size: 0, // Will be populated when league details are fetched
        scoring_type: league.sport || 'MLB',
        is_active: league.is_active !== undefined ? league.is_active : true,
        season: new Date().getFullYear(),
      }));
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
      setLoading('roster', true);
      setError('sync', null);

      try {
        // Get team ID
        const myTeamId = state.selectedLeague.my_team_id;

        if (!myTeamId) {
          throw new Error('User team ID not found for this league');
        }

        // Use enriched roster endpoint to get full player information
        const enrichedRoster = await fantraxApi.getEnrichedRoster(
          state.selectedLeague.league_id,
          myTeamId
        );

        console.log('Enriched roster data received:', enrichedRoster);

        // Transform to RosterData format
        // The enriched roster already has player names, teams, ages, etc.
        const rawPlayers = enrichedRoster.rosterItems || [];

        // Log first player to see data structure
        if (rawPlayers.length > 0) {
          console.log('Sample enriched player data:', rawPlayers[0]);
        }

        // Transform enriched player data to our format
        const players = rawPlayers.map((player: any) => ({
          player_id: player.id || player.playerId || player.player_id || '',
          player_name: player.name || player.playerName || player.player_name || 'Unknown Player',
          positions: player.positions || player.eligiblePositions || (player.position ? [player.position] : []),
          team: player.mlbTeam || player.team || player.mlb_team || '',
          age: player.age || null,
          status: player.status || player.injuryStatus || 'active',
          minor_league_eligible: player.minorLeagueEligible || player.minor_league_eligible || false,
          contract_years: player.contractYears || player.contract_years || null,
          contract_value: player.contractValue || player.contract_value || null,
        }));

        const roster: RosterData = {
          league_id: state.selectedLeague.league_id,
          team_id: myTeamId,
          team_name: enrichedRoster.team_name || state.selectedLeague.my_team_name || 'My Team',
          players: players,
          last_updated: new Date().toISOString(),
        };

        console.log(`Found ${roster.players.length} players for team ${roster.team_name}`);

        setState((prev) => ({ ...prev, roster }));
        console.log('Roster synced successfully for team:', roster.team_name);
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
