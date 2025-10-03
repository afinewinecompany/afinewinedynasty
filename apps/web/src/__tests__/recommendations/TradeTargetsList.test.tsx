/**
 * @jest-environment jsdom
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { TradeTargetsList } from '@/components/recommendations/TradeTargetsList';
import { useRecommendations } from '@/hooks/useRecommendations';
import type { TradeTargetsResponse } from '@/types/recommendations';

// Mock the hook
jest.mock('@/hooks/useRecommendations');

const mockUseRecommendations = useRecommendations as jest.MockedFunction<
  typeof useRecommendations
>;

describe('TradeTargetsList Component', () => {
  const mockLeagueId = 'test-league-123';

  const mockTradeTargets: TradeTargetsResponse = {
    buy_low_candidates: [
      {
        prospect_id: 1,
        name: 'Buy Low Prospect',
        position: 'SP',
        current_value: 'Low',
        target_value: 'Medium',
        reasoning: 'Undervalued due to injury',
        opportunity_type: 'buy_low',
      },
    ],
    sell_high_opportunities: [
      {
        prospect_id: 2,
        name: 'Sell High Prospect',
        position: 'OF',
        current_value: 'High',
        target_value: 'Medium',
        reasoning: 'Overperforming metrics',
        opportunity_type: 'sell_high',
      },
    ],
    trade_value_arbitrage: [
      {
        prospect_id: 3,
        name: 'Arbitrage Prospect',
        position: '3B',
        current_value: 'Medium',
        target_value: 'High',
        reasoning: 'Market inefficiency',
        opportunity_type: 'arbitrage',
      },
    ],
  };

  const defaultMockReturn = {
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
    fetchTeamNeeds: jest.fn(),
    fetchProspectRecommendations: jest.fn(),
    fetchTradeTargets: jest.fn(),
    fetchDraftStrategy: jest.fn(),
    fetchStashCandidates: jest.fn(),
    fetchPreferences: jest.fn(),
    updatePreferences: jest.fn(),
    clearAll: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockUseRecommendations.mockReturnValue(defaultMockReturn);
  });

  it('should render loading state', () => {
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      loading: { ...defaultMockReturn.loading, tradeTargets: true },
    });

    render(<TradeTargetsList leagueId={mockLeagueId} />);

    expect(
      screen.getByText('Finding trade opportunities...')
    ).toBeInTheDocument();
  });

  it('should render error state', () => {
    const errorMessage = 'Failed to load trade targets';
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      error: { ...defaultMockReturn.error, tradeTargets: errorMessage },
    });

    render(<TradeTargetsList leagueId={mockLeagueId} />);

    expect(screen.getByText(errorMessage)).toBeInTheDocument();
    expect(screen.getByText('Try Again')).toBeInTheDocument();
  });

  it('should render empty state when no data', () => {
    render(<TradeTargetsList leagueId={mockLeagueId} autoLoad={false} />);

    expect(screen.getByText('No trade targets available')).toBeInTheDocument();
    expect(screen.getByText('Load Trade Targets')).toBeInTheDocument();
  });

  it('should display all trade targets correctly', () => {
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      tradeTargets: mockTradeTargets,
    });

    render(<TradeTargetsList leagueId={mockLeagueId} />);

    // Check title
    expect(screen.getByText('Trade Targets')).toBeInTheDocument();

    // Check buy low candidates
    expect(screen.getByText('Buy Low Candidates')).toBeInTheDocument();
    expect(screen.getByText('Buy Low Prospect')).toBeInTheDocument();
    expect(screen.getByText('Undervalued due to injury')).toBeInTheDocument();

    // Check sell high opportunities
    expect(screen.getByText('Sell High Opportunities')).toBeInTheDocument();
    expect(screen.getByText('Sell High Prospect')).toBeInTheDocument();
    expect(screen.getByText('Overperforming metrics')).toBeInTheDocument();

    // Check arbitrage
    expect(screen.getByText('Value Arbitrage')).toBeInTheDocument();
    expect(screen.getByText('Arbitrage Prospect')).toBeInTheDocument();
    expect(screen.getByText('Market inefficiency')).toBeInTheDocument();
  });

  it('should filter by buy_low category', () => {
    const mockFetch = jest.fn();
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      tradeTargets: mockTradeTargets,
      fetchTradeTargets: mockFetch,
    });

    render(<TradeTargetsList leagueId={mockLeagueId} />);

    const buyLowButton = screen.getByRole('button', { name: /Buy Low/i });
    fireEvent.click(buyLowButton);

    expect(mockFetch).toHaveBeenCalledWith(mockLeagueId, {
      category: 'buy_low',
    });
  });

  it('should filter by sell_high category', () => {
    const mockFetch = jest.fn();
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      tradeTargets: mockTradeTargets,
      fetchTradeTargets: mockFetch,
    });

    render(<TradeTargetsList leagueId={mockLeagueId} />);

    const sellHighButton = screen.getByRole('button', { name: /Sell High/i });
    fireEvent.click(sellHighButton);

    expect(mockFetch).toHaveBeenCalledWith(mockLeagueId, {
      category: 'sell_high',
    });
  });

  it('should filter by arbitrage category', () => {
    const mockFetch = jest.fn();
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      tradeTargets: mockTradeTargets,
      fetchTradeTargets: mockFetch,
    });

    render(<TradeTargetsList leagueId={mockLeagueId} />);

    const arbitrageButton = screen.getByRole('button', { name: /Arbitrage/i });
    fireEvent.click(arbitrageButton);

    expect(mockFetch).toHaveBeenCalledWith(mockLeagueId, {
      category: 'arbitrage',
    });
  });

  it('should show all categories when All filter is selected', () => {
    const mockFetch = jest.fn();
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      tradeTargets: mockTradeTargets,
      fetchTradeTargets: mockFetch,
    });

    render(<TradeTargetsList leagueId={mockLeagueId} />);

    // First set to a category
    const buyLowButton = screen.getByRole('button', { name: /Buy Low/i });
    fireEvent.click(buyLowButton);

    // Then set to All
    const allButton = screen.getByRole('button', { name: /^All$/i });
    fireEvent.click(allButton);

    expect(mockFetch).toHaveBeenLastCalledWith(mockLeagueId, undefined);
  });

  it('should call onProspectClick when candidate is clicked', () => {
    const mockOnClick = jest.fn();
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      tradeTargets: mockTradeTargets,
    });

    render(
      <TradeTargetsList leagueId={mockLeagueId} onProspectClick={mockOnClick} />
    );

    const candidate = screen.getByText('Buy Low Prospect');
    fireEvent.click(candidate);

    expect(mockOnClick).toHaveBeenCalledWith(1);
  });

  it('should call onRefresh callback when refresh button is clicked', () => {
    const mockOnRefresh = jest.fn();
    const mockFetch = jest.fn();
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      tradeTargets: mockTradeTargets,
      fetchTradeTargets: mockFetch,
    });

    render(
      <TradeTargetsList leagueId={mockLeagueId} onRefresh={mockOnRefresh} />
    );

    const refreshButton = screen.getByText('Refresh');
    fireEvent.click(refreshButton);

    expect(mockOnRefresh).toHaveBeenCalled();
    expect(mockFetch).toHaveBeenCalled();
  });

  it('should display empty message when no targets found', () => {
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      tradeTargets: {
        buy_low_candidates: [],
        sell_high_opportunities: [],
        trade_value_arbitrage: [],
      },
    });

    render(<TradeTargetsList leagueId={mockLeagueId} />);

    expect(screen.getByText('No trade targets found')).toBeInTheDocument();
  });

  it('should display value comparison correctly', () => {
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      tradeTargets: mockTradeTargets,
    });

    render(<TradeTargetsList leagueId={mockLeagueId} />);

    // Check current and target values (multiple occurrences)
    expect(screen.getAllByText('Current Value').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Target Value').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Low').length).toBeGreaterThan(0);
  });

  it('should auto-load on mount when autoLoad is true', () => {
    const mockFetch = jest.fn();
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      fetchTradeTargets: mockFetch,
    });

    render(<TradeTargetsList leagueId={mockLeagueId} autoLoad={true} />);

    expect(mockFetch).toHaveBeenCalledWith(mockLeagueId);
  });

  it('should not auto-load on mount when autoLoad is false', () => {
    const mockFetch = jest.fn();
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      fetchTradeTargets: mockFetch,
    });

    render(<TradeTargetsList leagueId={mockLeagueId} autoLoad={false} />);

    expect(mockFetch).not.toHaveBeenCalled();
  });
});
