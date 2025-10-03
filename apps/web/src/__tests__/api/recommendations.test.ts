/**
 * API client tests for recommendations endpoints
 *
 * Tests all 7 API client functions with mock responses
 */

import {
  getTeamNeeds,
  getProspectRecommendations,
  getTradeTargets,
  getDraftStrategy,
  getStashCandidates,
  getUserPreferences,
  updateUserPreferences,
} from '@/lib/api/recommendations';
import { apiClient } from '@/lib/api/client';
import type {
  TeamNeeds,
  ProspectRecommendationsResponse,
  TradeTargetsResponse,
  DraftStrategyResponse,
  StashCandidatesResponse,
  UserPreferences,
} from '@/types/recommendations';

// Mock the API client
jest.mock('@/lib/api/client');

const mockApiClient = apiClient as jest.Mocked<typeof apiClient>;

describe('Recommendations API Client', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('getTeamNeeds', () => {
    it('should call apiClient.get with correct endpoint and cache TTL', async () => {
      const mockTeamNeeds: TeamNeeds = {
        positional_needs: [{ position: 'SP', severity: 'critical', timeline: 'immediate' }],
        depth_analysis: { SP: { starters: 2, depth: 1, gap_score: 75 } },
        competitive_window: 'contending',
        future_needs: { '2_year': ['C'], '3_year': ['SS'] },
      };

      mockApiClient.get.mockResolvedValue(mockTeamNeeds);

      const result = await getTeamNeeds('test-league-123');

      expect(mockApiClient.get).toHaveBeenCalledWith(
        '/api/recommendations/team-needs/test-league-123',
        60 // 1 hour cache
      );
      expect(result).toEqual(mockTeamNeeds);
    });

    it('should handle API errors', async () => {
      mockApiClient.get.mockRejectedValue(new Error('Network error'));

      await expect(getTeamNeeds('test-league-123')).rejects.toThrow('Network error');
    });
  });

  describe('getProspectRecommendations', () => {
    it('should call apiClient.get with correct endpoint and no query params', async () => {
      const mockRecommendations: ProspectRecommendationsResponse = {
        recommendations: [
          {
            prospect_id: 1,
            fit_score: 85,
            position_fit: 90,
            timeline_fit: 80,
            value_rating: 'High',
            explanation: 'Great fit for your team',
            confidence: 'high',
          },
        ],
      };

      mockApiClient.get.mockResolvedValue(mockRecommendations);

      const result = await getProspectRecommendations('test-league-123');

      expect(mockApiClient.get).toHaveBeenCalledWith(
        '/api/recommendations/prospects/test-league-123',
        30 // 30 minutes cache
      );
      expect(result).toEqual(mockRecommendations);
    });

    it('should call apiClient.get with query parameters', async () => {
      const mockRecommendations: ProspectRecommendationsResponse = {
        recommendations: [],
      };

      mockApiClient.get.mockResolvedValue(mockRecommendations);

      await getProspectRecommendations('test-league-123', {
        limit: 20,
        risk_tolerance: 'balanced',
      });

      expect(mockApiClient.get).toHaveBeenCalledWith(
        '/api/recommendations/prospects/test-league-123?limit=20&risk_tolerance=balanced',
        30
      );
    });

    it('should handle limit parameter only', async () => {
      mockApiClient.get.mockResolvedValue({ recommendations: [] });

      await getProspectRecommendations('test-league-123', { limit: 10 });

      expect(mockApiClient.get).toHaveBeenCalledWith(
        '/api/recommendations/prospects/test-league-123?limit=10',
        30
      );
    });

    it('should handle risk_tolerance parameter only', async () => {
      mockApiClient.get.mockResolvedValue({ recommendations: [] });

      await getProspectRecommendations('test-league-123', { risk_tolerance: 'aggressive' });

      expect(mockApiClient.get).toHaveBeenCalledWith(
        '/api/recommendations/prospects/test-league-123?risk_tolerance=aggressive',
        30
      );
    });
  });

  describe('getTradeTargets', () => {
    it('should call apiClient.get with correct endpoint and no query params', async () => {
      const mockTradeTargets: TradeTargetsResponse = {
        buy_low_candidates: [],
        sell_high_opportunities: [],
        trade_value_arbitrage: [],
      };

      mockApiClient.get.mockResolvedValue(mockTradeTargets);

      const result = await getTradeTargets('test-league-123');

      expect(mockApiClient.get).toHaveBeenCalledWith(
        '/api/recommendations/trade-targets/test-league-123',
        30
      );
      expect(result).toEqual(mockTradeTargets);
    });

    it('should call apiClient.get with category filter', async () => {
      const mockTradeTargets: TradeTargetsResponse = {
        buy_low_candidates: [
          {
            prospect_id: 1,
            name: 'Buy Low Prospect',
            position: 'OF',
            current_value: 50,
            projected_value: 75,
            reasoning: 'Undervalued due to recent slump',
          },
        ],
        sell_high_opportunities: [],
        trade_value_arbitrage: [],
      };

      mockApiClient.get.mockResolvedValue(mockTradeTargets);

      await getTradeTargets('test-league-123', { category: 'buy_low' });

      expect(mockApiClient.get).toHaveBeenCalledWith(
        '/api/recommendations/trade-targets/test-league-123?category=buy_low',
        30
      );
    });

    it('should handle sell_high category', async () => {
      mockApiClient.get.mockResolvedValue({
        buy_low_candidates: [],
        sell_high_opportunities: [],
        trade_value_arbitrage: [],
      });

      await getTradeTargets('test-league-123', { category: 'sell_high' });

      expect(mockApiClient.get).toHaveBeenCalledWith(
        '/api/recommendations/trade-targets/test-league-123?category=sell_high',
        30
      );
    });
  });

  describe('getDraftStrategy', () => {
    it('should call apiClient.get with correct endpoint and no query params', async () => {
      const mockDraftStrategy: DraftStrategyResponse = {
        tier_1: [],
        tier_2: [],
        tier_3: [],
        bpa_vs_need: 'Take BPA',
        sleepers: [],
      };

      mockApiClient.get.mockResolvedValue(mockDraftStrategy);

      const result = await getDraftStrategy('test-league-123');

      expect(mockApiClient.get).toHaveBeenCalledWith(
        '/api/recommendations/draft-strategy/test-league-123',
        30
      );
      expect(result).toEqual(mockDraftStrategy);
    });

    it('should call apiClient.get with pick_number parameter', async () => {
      const mockDraftStrategy: DraftStrategyResponse = {
        tier_1: [
          {
            prospect_id: 1,
            name: 'Top Prospect',
            position: 'SP',
            draft_value: 'High',
            need_match: 90,
          },
        ],
        tier_2: [],
        tier_3: [],
        bpa_vs_need: 'Take need - SP is critical',
        sleepers: [],
      };

      mockApiClient.get.mockResolvedValue(mockDraftStrategy);

      await getDraftStrategy('test-league-123', { pick_number: 5 });

      expect(mockApiClient.get).toHaveBeenCalledWith(
        '/api/recommendations/draft-strategy/test-league-123?pick_number=5',
        30
      );
    });

    it('should handle different pick numbers', async () => {
      mockApiClient.get.mockResolvedValue({
        tier_1: [],
        tier_2: [],
        tier_3: [],
        bpa_vs_need: 'Strategy',
        sleepers: [],
      });

      await getDraftStrategy('test-league-123', { pick_number: 12 });

      expect(mockApiClient.get).toHaveBeenCalledWith(
        '/api/recommendations/draft-strategy/test-league-123?pick_number=12',
        30
      );
    });
  });

  describe('getStashCandidates', () => {
    it('should call apiClient.get with correct endpoint and cache TTL', async () => {
      const mockStashCandidates: StashCandidatesResponse = {
        available_spots: 3,
        stash_candidates: [
          {
            prospect_id: 1,
            name: 'Stash Prospect',
            position: 'OF',
            upside_score: 85,
            eta: '2026',
            reasoning: 'High upside power/speed combo',
          },
        ],
      };

      mockApiClient.get.mockResolvedValue(mockStashCandidates);

      const result = await getStashCandidates('test-league-123');

      expect(mockApiClient.get).toHaveBeenCalledWith(
        '/api/recommendations/stash-candidates/test-league-123',
        30
      );
      expect(result).toEqual(mockStashCandidates);
    });

    it('should handle empty stash candidates', async () => {
      const mockStashCandidates: StashCandidatesResponse = {
        available_spots: 0,
        stash_candidates: [],
      };

      mockApiClient.get.mockResolvedValue(mockStashCandidates);

      const result = await getStashCandidates('test-league-123');

      expect(result.available_spots).toBe(0);
      expect(result.stash_candidates).toHaveLength(0);
    });
  });

  describe('getUserPreferences', () => {
    it('should call apiClient.get with correct endpoint', async () => {
      const mockPreferences: UserPreferences = {
        risk_tolerance: 'balanced',
        prefer_win_now: true,
        prefer_rebuild: false,
        position_priorities: ['SP', 'OF'],
        prefer_buy_low: true,
        prefer_sell_high: false,
      };

      mockApiClient.get.mockResolvedValue(mockPreferences);

      const result = await getUserPreferences();

      expect(mockApiClient.get).toHaveBeenCalledWith('/api/recommendations/preferences');
      expect(result).toEqual(mockPreferences);
    });

    it('should handle different preference combinations', async () => {
      const mockPreferences: UserPreferences = {
        risk_tolerance: 'aggressive',
        prefer_win_now: false,
        prefer_rebuild: true,
        position_priorities: ['C', '2B', 'SS'],
        prefer_buy_low: false,
        prefer_sell_high: true,
      };

      mockApiClient.get.mockResolvedValue(mockPreferences);

      const result = await getUserPreferences();

      expect(result.risk_tolerance).toBe('aggressive');
      expect(result.prefer_rebuild).toBe(true);
      expect(result.position_priorities).toEqual(['C', '2B', 'SS']);
    });
  });

  describe('updateUserPreferences', () => {
    it('should call apiClient.put with correct endpoint and data', async () => {
      const preferencesToUpdate: UserPreferences = {
        risk_tolerance: 'aggressive',
        prefer_win_now: true,
        prefer_rebuild: false,
        position_priorities: ['SP', 'C'],
        prefer_buy_low: true,
        prefer_sell_high: true,
      };

      const mockUpdatedPreferences: UserPreferences = {
        ...preferencesToUpdate,
      };

      mockApiClient.put.mockResolvedValue(mockUpdatedPreferences);

      const result = await updateUserPreferences(preferencesToUpdate);

      expect(mockApiClient.put).toHaveBeenCalledWith(
        '/api/recommendations/preferences',
        preferencesToUpdate
      );
      expect(result).toEqual(mockUpdatedPreferences);
    });

    it('should handle preference update errors', async () => {
      const preferences: UserPreferences = {
        risk_tolerance: 'balanced',
        prefer_win_now: false,
        prefer_rebuild: true,
        position_priorities: [],
        prefer_buy_low: false,
        prefer_sell_high: false,
      };

      mockApiClient.put.mockRejectedValue(new Error('Validation error'));

      await expect(updateUserPreferences(preferences)).rejects.toThrow('Validation error');
    });

    it('should handle empty position priorities', async () => {
      const preferences: UserPreferences = {
        risk_tolerance: 'conservative',
        prefer_win_now: true,
        prefer_rebuild: false,
        position_priorities: [],
        prefer_buy_low: false,
        prefer_sell_high: false,
      };

      mockApiClient.put.mockResolvedValue(preferences);

      const result = await updateUserPreferences(preferences);

      expect(result.position_priorities).toEqual([]);
    });
  });

  describe('Integration scenarios', () => {
    it('should handle sequential API calls', async () => {
      mockApiClient.get.mockResolvedValueOnce({ recommendations: [] });
      mockApiClient.get.mockResolvedValueOnce({
        available_spots: 2,
        stash_candidates: [],
      });

      await getProspectRecommendations('league-1');
      await getStashCandidates('league-1');

      expect(mockApiClient.get).toHaveBeenCalledTimes(2);
    });

    it('should handle concurrent API calls', async () => {
      mockApiClient.get.mockResolvedValue({ recommendations: [] });

      const promises = [
        getProspectRecommendations('league-1'),
        getProspectRecommendations('league-2'),
        getProspectRecommendations('league-3'),
      ];

      await Promise.all(promises);

      expect(mockApiClient.get).toHaveBeenCalledTimes(3);
    });
  });
});
