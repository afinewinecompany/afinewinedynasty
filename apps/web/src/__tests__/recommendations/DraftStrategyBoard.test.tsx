/**
 * @jest-environment jsdom
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { DraftStrategyBoard } from '@/components/recommendations/DraftStrategyBoard';
import { useRecommendations } from '@/hooks/useRecommendations';
import type { DraftStrategy } from '@/types/recommendations';

// Mock the hook
jest.mock('@/hooks/useRecommendations');

const mockUseRecommendations = useRecommendations as jest.MockedFunction<
  typeof useRecommendations
>;

describe('DraftStrategyBoard Component', () => {
  const mockLeagueId = 'test-league-123';

  const mockDraftStrategy: DraftStrategy = {
    tier_1: [
      {
        prospect_id: 1,
        name: 'Elite Prospect 1',
        position: 'SP',
        draft_value: 'High',
        need_match: 85,
      },
      {
        prospect_id: 2,
        name: 'Elite Prospect 2',
        position: 'OF',
        draft_value: 'High',
        need_match: 90,
      },
    ],
    tier_2: [
      {
        prospect_id: 3,
        name: 'Good Prospect 1',
        position: '2B',
        draft_value: 'Medium',
        need_match: 70,
      },
    ],
    tier_3: [
      {
        prospect_id: 4,
        name: 'Solid Prospect 1',
        position: 'C',
        draft_value: 'Low',
        need_match: 50,
      },
    ],
    bpa_vs_need: 'Take BPA - Elite talent available at position of need',
    sleepers: [
      {
        prospect_id: 5,
        name: 'Sleeper Prospect 1',
        position: '3B',
        draft_value: 'Sleeper',
        need_match: 60,
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
      loading: { ...defaultMockReturn.loading, draftStrategy: true },
    });

    render(<DraftStrategyBoard leagueId={mockLeagueId} />);

    expect(
      screen.getByText('Generating draft strategy...')
    ).toBeInTheDocument();
  });

  it('should render error state', () => {
    const errorMessage = 'Failed to load draft strategy';
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      error: { ...defaultMockReturn.error, draftStrategy: errorMessage },
    });

    render(<DraftStrategyBoard leagueId={mockLeagueId} />);

    expect(screen.getByText(errorMessage)).toBeInTheDocument();
    expect(screen.getByText('Try Again')).toBeInTheDocument();
  });

  it('should render empty state when no data', () => {
    render(<DraftStrategyBoard leagueId={mockLeagueId} autoLoad={false} />);

    expect(screen.getByText('No draft strategy available')).toBeInTheDocument();
    expect(screen.getByText('Load Draft Strategy')).toBeInTheDocument();
  });

  it('should display draft strategy data correctly', () => {
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      draftStrategy: mockDraftStrategy,
    });

    render(<DraftStrategyBoard leagueId={mockLeagueId} />);

    // Check title
    expect(screen.getByText('Draft Strategy Board')).toBeInTheDocument();
    expect(
      screen.getByText('Tiered prospects and draft recommendations')
    ).toBeInTheDocument();

    // Check BPA vs Need guidance
    expect(screen.getByText('Draft Guidance')).toBeInTheDocument();
    expect(screen.getByText(mockDraftStrategy.bpa_vs_need)).toBeInTheDocument();

    // Check tier headers
    expect(screen.getByText('Tier 1')).toBeInTheDocument();
    expect(screen.getByText('Tier 2')).toBeInTheDocument();
    expect(screen.getByText('Tier 3')).toBeInTheDocument();

    // Check prospects
    expect(screen.getByText('Elite Prospect 1')).toBeInTheDocument();
    expect(screen.getByText('Elite Prospect 2')).toBeInTheDocument();
    expect(screen.getByText('Good Prospect 1')).toBeInTheDocument();
    expect(screen.getByText('Solid Prospect 1')).toBeInTheDocument();

    // Check sleepers
    expect(screen.getByText('Sleeper Candidates')).toBeInTheDocument();
    expect(screen.getByText('Sleeper Prospect 1')).toBeInTheDocument();
  });

  it('should call fetchDraftStrategy on mount when autoLoad is true', () => {
    const mockFetch = jest.fn();
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      fetchDraftStrategy: mockFetch,
    });

    render(<DraftStrategyBoard leagueId={mockLeagueId} autoLoad={true} />);

    expect(mockFetch).toHaveBeenCalledWith(mockLeagueId, undefined);
  });

  it('should not call fetchDraftStrategy on mount when autoLoad is false', () => {
    const mockFetch = jest.fn();
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      fetchDraftStrategy: mockFetch,
    });

    render(<DraftStrategyBoard leagueId={mockLeagueId} autoLoad={false} />);

    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('should call fetchDraftStrategy when refresh button is clicked', () => {
    const mockFetch = jest.fn();
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      draftStrategy: mockDraftStrategy,
      fetchDraftStrategy: mockFetch,
    });

    render(<DraftStrategyBoard leagueId={mockLeagueId} />);

    const refreshButton = screen.getByText('Refresh');
    fireEvent.click(refreshButton);

    expect(mockFetch).toHaveBeenCalledWith(mockLeagueId, undefined);
  });

  it('should handle pick number input and update', () => {
    const mockFetch = jest.fn();
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      draftStrategy: mockDraftStrategy,
      fetchDraftStrategy: mockFetch,
    });

    render(<DraftStrategyBoard leagueId={mockLeagueId} />);

    // Find input and update button
    const input = screen.getByPlaceholderText('Enter pick number...');
    const updateButton = screen.getByText('Update');

    // Enter pick number
    fireEvent.change(input, { target: { value: '5' } });
    fireEvent.click(updateButton);

    expect(mockFetch).toHaveBeenCalledWith(mockLeagueId, { pick_number: 5 });
  });

  it('should handle pick number input with Enter key', () => {
    const mockFetch = jest.fn();
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      draftStrategy: mockDraftStrategy,
      fetchDraftStrategy: mockFetch,
    });

    render(<DraftStrategyBoard leagueId={mockLeagueId} />);

    // Find input
    const input = screen.getByPlaceholderText('Enter pick number...');

    // Enter pick number and press Enter
    fireEvent.change(input, { target: { value: '7' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    expect(mockFetch).toHaveBeenCalledWith(mockLeagueId, { pick_number: 7 });
  });

  it('should use initialPickNumber prop if provided', () => {
    const mockFetch = jest.fn();
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      fetchDraftStrategy: mockFetch,
    });

    render(
      <DraftStrategyBoard
        leagueId={mockLeagueId}
        initialPickNumber={3}
        autoLoad={true}
      />
    );

    expect(mockFetch).toHaveBeenCalledWith(mockLeagueId, { pick_number: 3 });
  });

  it('should call onProspectClick when prospect is clicked', () => {
    const mockOnClick = jest.fn();
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      draftStrategy: mockDraftStrategy,
    });

    render(
      <DraftStrategyBoard
        leagueId={mockLeagueId}
        onProspectClick={mockOnClick}
      />
    );

    // Click on a prospect
    const prospect = screen.getByText('Elite Prospect 1');
    fireEvent.click(prospect.closest('div')!);

    expect(mockOnClick).toHaveBeenCalledWith(1);
  });

  it('should call onRefresh callback when provided', () => {
    const mockOnRefresh = jest.fn();
    const mockFetch = jest.fn();
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      draftStrategy: mockDraftStrategy,
      fetchDraftStrategy: mockFetch,
    });

    render(
      <DraftStrategyBoard leagueId={mockLeagueId} onRefresh={mockOnRefresh} />
    );

    const refreshButton = screen.getByText('Refresh');
    fireEvent.click(refreshButton);

    expect(mockOnRefresh).toHaveBeenCalled();
  });

  it('should display tier badges correctly', () => {
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      draftStrategy: mockDraftStrategy,
    });

    render(<DraftStrategyBoard leagueId={mockLeagueId} />);

    // Check tier counts in badges
    const tier1Badge = screen.getByText('Tier 1').parentElement;
    expect(tier1Badge).toHaveTextContent('2'); // 2 tier 1 prospects

    const tier2Badge = screen.getByText('Tier 2').parentElement;
    expect(tier2Badge).toHaveTextContent('1'); // 1 tier 2 prospect
  });

  it('should display need match percentages correctly', () => {
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      draftStrategy: mockDraftStrategy,
    });

    render(<DraftStrategyBoard leagueId={mockLeagueId} />);

    // Check need match percentages are displayed
    expect(screen.getByText('85%')).toBeInTheDocument();
    expect(screen.getByText('90%')).toBeInTheDocument();
    expect(screen.getByText('70%')).toBeInTheDocument();
  });

  it('should handle empty tier arrays', () => {
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      draftStrategy: {
        tier_1: [],
        tier_2: [],
        tier_3: [],
        bpa_vs_need: 'Draft based on team needs',
        sleepers: [],
      },
    });

    render(<DraftStrategyBoard leagueId={mockLeagueId} />);

    // Should still show BPA guidance but no tier sections
    expect(screen.getByText('Draft Guidance')).toBeInTheDocument();
    expect(screen.getByText('Draft based on team needs')).toBeInTheDocument();

    // No tier headers should be visible
    expect(screen.queryByText('Tier 1')).not.toBeInTheDocument();
    expect(screen.queryByText('Tier 2')).not.toBeInTheDocument();
    expect(screen.queryByText('Sleeper Candidates')).not.toBeInTheDocument();
  });

  it('should handle invalid pick number input', () => {
    const mockFetch = jest.fn();
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      draftStrategy: mockDraftStrategy,
      fetchDraftStrategy: mockFetch,
    });

    render(<DraftStrategyBoard leagueId={mockLeagueId} />);

    const input = screen.getByPlaceholderText('Enter pick number...');
    const updateButton = screen.getByText('Update');

    // Clear the input (empty string)
    fireEvent.change(input, { target: { value: '' } });
    fireEvent.click(updateButton);

    // Should call without pick_number parameter
    expect(mockFetch).toHaveBeenCalledWith(mockLeagueId);
  });
});
