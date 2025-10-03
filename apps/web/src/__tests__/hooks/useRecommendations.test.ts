/**
 * @jest-environment jsdom
 */
import { renderHook, act, waitFor } from '@testing-library/react';
import { useRecommendations } from '@/hooks/useRecommendations';
import * as recommendationsApi from '@/lib/api/recommendations';
import type {
  TeamNeeds,
  ProspectRecommendationsResponse,
  TradeTargetsResponse,
  DraftStrategyResponse,
  StashCandidatesResponse,
  UserPreferences,
} from '@/types/recommendations';

// Mock the API module
jest.mock('@/lib/api/recommendations');

describe('useRecommendations Hook', () => {
  const mockLeagueId = 'test-league-123';

  const mockTeamNeeds: TeamNeeds = {
    positional_needs: [
      { position: 'SP', severity: 'high', timeline: 'immediate' },
    ],
    depth_analysis: {
      SP: { starters: 2, depth: 1, gap_score: 60 },
    },
    competitive_window: 'contending',
    future_needs: {
      '2_year': ['OF'],
      '3_year': ['C'],
    },
  };

  const mockProspectRecommendations: ProspectRecommendationsResponse = {
    recommendations: [
      {
        prospect_id: 1,
        fit_score: 85,
        position_fit: 90,
        timeline_fit: 80,
        value_rating: 'high',
        explanation: 'Great fit for your team',
        confidence: 'high',
      },
    ],
  };

  const mockTradeTargets: TradeTargetsResponse = {
    buy_low_candidates: [
      {
        prospect_id: 2,
        name: 'Test Prospect',
        position: 'OF',
        current_value: 'Medium',
        target_value: 'High',
        reasoning: 'Undervalued',
        opportunity_type: 'buy_low',
      },
    ],
    sell_high_opportunities: [],
    trade_value_arbitrage: [],
  };

  const mockDraftStrategy: DraftStrategyResponse = {
    tier_1: [
      {
        prospect_id: 3,
        name: 'Top Prospect',
        position: 'SP',
        draft_value: 'Elite',
        need_match: 95,
      },
    ],
    tier_2: [],
    bpa_vs_need: 'Draft best player available',
    sleepers: [],
  };

  const mockStashCandidates: StashCandidatesResponse = {
    available_spots: 2,
    stash_candidates: [
      {
        prospect_id: 4,
        name: 'Stash Candidate',
        position: '2B',
        upside_score: 75,
        eta: 2026,
        reasoning: 'High upside',
      },
    ],
  };

  const mockPreferences: UserPreferences = {
    risk_tolerance: 'balanced',
    prefer_win_now: false,
    prefer_rebuild: true,
    position_priorities: ['SP', 'OF'],
    prefer_buy_low: true,
    prefer_sell_high: false,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('fetchTeamNeeds', () => {
    it('should fetch team needs successfully', async () => {
      (recommendationsApi.getTeamNeeds as jest.Mock).mockResolvedValue(mockTeamNeeds);

      const { result } = renderHook(() => useRecommendations());

      expect(result.current.loading.teamNeeds).toBe(false);
      expect(result.current.teamNeeds).toBeNull();

      await act(async () => {
        await result.current.fetchTeamNeeds(mockLeagueId);
      });

      expect(recommendationsApi.getTeamNeeds).toHaveBeenCalledWith(mockLeagueId);
      expect(result.current.teamNeeds).toEqual(mockTeamNeeds);
      expect(result.current.loading.teamNeeds).toBe(false);
      expect(result.current.error.teamNeeds).toBeNull();
    });

    it('should handle error when fetching team needs', async () => {
      const errorMessage = 'Failed to fetch team needs';
      (recommendationsApi.getTeamNeeds as jest.Mock).mockRejectedValue(new Error(errorMessage));

      const { result } = renderHook(() => useRecommendations());

      await act(async () => {
        await result.current.fetchTeamNeeds(mockLeagueId);
      });

      expect(result.current.teamNeeds).toBeNull();
      expect(result.current.error.teamNeeds).toBe(errorMessage);
    });
  });

  describe('fetchProspectRecommendations', () => {
    it('should fetch prospect recommendations with query params', async () => {
      (recommendationsApi.getProspectRecommendations as jest.Mock).mockResolvedValue(
        mockProspectRecommendations
      );

      const { result } = renderHook(() => useRecommendations());

      await act(async () => {
        await result.current.fetchProspectRecommendations(mockLeagueId, {
          limit: 20,
          risk_tolerance: 'aggressive',
        });
      });

      expect(recommendationsApi.getProspectRecommendations).toHaveBeenCalledWith(
        mockLeagueId,
        { limit: 20, risk_tolerance: 'aggressive' }
      );
      expect(result.current.prospectRecommendations).toEqual(
        mockProspectRecommendations.recommendations
      );
    });
  });

  describe('fetchTradeTargets', () => {
    it('should fetch trade targets successfully', async () => {
      (recommendationsApi.getTradeTargets as jest.Mock).mockResolvedValue(mockTradeTargets);

      const { result } = renderHook(() => useRecommendations());

      await act(async () => {
        await result.current.fetchTradeTargets(mockLeagueId);
      });

      expect(result.current.tradeTargets).toEqual(mockTradeTargets);
    });
  });

  describe('fetchDraftStrategy', () => {
    it('should fetch draft strategy with pick number', async () => {
      (recommendationsApi.getDraftStrategy as jest.Mock).mockResolvedValue(mockDraftStrategy);

      const { result } = renderHook(() => useRecommendations());

      await act(async () => {
        await result.current.fetchDraftStrategy(mockLeagueId, { pick_number: 5 });
      });

      expect(recommendationsApi.getDraftStrategy).toHaveBeenCalledWith(mockLeagueId, {
        pick_number: 5,
      });
      expect(result.current.draftStrategy).toEqual(mockDraftStrategy);
    });
  });

  describe('fetchStashCandidates', () => {
    it('should fetch stash candidates successfully', async () => {
      (recommendationsApi.getStashCandidates as jest.Mock).mockResolvedValue(
        mockStashCandidates
      );

      const { result } = renderHook(() => useRecommendations());

      await act(async () => {
        await result.current.fetchStashCandidates(mockLeagueId);
      });

      expect(result.current.stashCandidates).toEqual(mockStashCandidates);
    });
  });

  describe('fetchPreferences', () => {
    it('should fetch user preferences successfully', async () => {
      (recommendationsApi.getUserPreferences as jest.Mock).mockResolvedValue(mockPreferences);

      const { result } = renderHook(() => useRecommendations());

      await act(async () => {
        await result.current.fetchPreferences();
      });

      expect(result.current.preferences).toEqual(mockPreferences);
    });
  });

  describe('updatePreferences', () => {
    it('should update user preferences successfully', async () => {
      const updatedPreferences = { ...mockPreferences, risk_tolerance: 'aggressive' as const };
      (recommendationsApi.updateUserPreferences as jest.Mock).mockResolvedValue(
        updatedPreferences
      );

      const { result } = renderHook(() => useRecommendations());

      await act(async () => {
        await result.current.updatePreferences(updatedPreferences);
      });

      expect(recommendationsApi.updateUserPreferences).toHaveBeenCalledWith(updatedPreferences);
      expect(result.current.preferences).toEqual(updatedPreferences);
    });

    it('should handle error on update failure', async () => {
      const errorMessage = 'Failed to update preferences';
      (recommendationsApi.updateUserPreferences as jest.Mock).mockRejectedValue(
        new Error(errorMessage)
      );

      const { result } = renderHook(() => useRecommendations());

      await act(async () => {
        try {
          await result.current.updatePreferences(mockPreferences);
        } catch (err) {
          // Error is expected and re-thrown by hook
        }
      });

      // Check that error state was set
      expect(result.current.error.preferences).toBe(errorMessage);
    });
  });

  describe('clearAll', () => {
    it('should clear all data and errors', async () => {
      (recommendationsApi.getTeamNeeds as jest.Mock).mockResolvedValue(mockTeamNeeds);

      const { result } = renderHook(() => useRecommendations());

      // Load some data
      await act(async () => {
        await result.current.fetchTeamNeeds(mockLeagueId);
      });

      expect(result.current.teamNeeds).not.toBeNull();

      // Clear all
      act(() => {
        result.current.clearAll();
      });

      expect(result.current.teamNeeds).toBeNull();
      expect(result.current.prospectRecommendations).toEqual([]);
      expect(result.current.tradeTargets).toBeNull();
      expect(result.current.draftStrategy).toBeNull();
      expect(result.current.stashCandidates).toBeNull();
      expect(result.current.preferences).toBeNull();
    });
  });
});
