/**
 * @jest-environment jsdom
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { StashCandidates } from '@/components/recommendations/StashCandidates';
import { useRecommendations } from '@/hooks/useRecommendations';
import type { StashCandidatesResponse } from '@/types/recommendations';

// Mock the hook
jest.mock('@/hooks/useRecommendations');

const mockUseRecommendations = useRecommendations as jest.MockedFunction<
  typeof useRecommendations
>;

describe('StashCandidates Component', () => {
  const mockLeagueId = 'test-league-123';

  const mockStashCandidates: StashCandidatesResponse = {
    available_spots: 3,
    stash_candidates: [
      {
        prospect_id: 1,
        name: 'Elite Stash 1',
        position: 'SP',
        upside_score: 85,
        eta: '2026',
        reasoning: 'Elite pitching prospect with ace potential',
      },
      {
        prospect_id: 2,
        name: 'High Upside 2',
        position: 'OF',
        upside_score: 70,
        eta: '2025',
        reasoning: 'Power/speed combination with high ceiling',
      },
      {
        prospect_id: 3,
        name: 'Moderate Upside 3',
        position: '2B',
        upside_score: 50,
        eta: '2027',
        reasoning: 'Solid contact skills with developing power',
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
      loading: { ...defaultMockReturn.loading, stashCandidates: true },
    });

    render(<StashCandidates leagueId={mockLeagueId} />);

    expect(screen.getByText('Finding stash candidates...')).toBeInTheDocument();
  });

  it('should render error state', () => {
    const errorMessage = 'Failed to load stash candidates';
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      error: { ...defaultMockReturn.error, stashCandidates: errorMessage },
    });

    render(<StashCandidates leagueId={mockLeagueId} />);

    expect(screen.getByText(errorMessage)).toBeInTheDocument();
    expect(screen.getByText('Try Again')).toBeInTheDocument();
  });

  it('should render empty state when no data', () => {
    render(<StashCandidates leagueId={mockLeagueId} autoLoad={false} />);

    expect(
      screen.getByText('No stash candidates available')
    ).toBeInTheDocument();
    expect(screen.getByText('Load Stash Candidates')).toBeInTheDocument();
  });

  it('should display stash candidates data correctly', () => {
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      stashCandidates: mockStashCandidates,
    });

    render(<StashCandidates leagueId={mockLeagueId} />);

    // Check title
    expect(screen.getByText('Stash Candidates')).toBeInTheDocument();
    expect(
      screen.getByText('High-upside prospects to stash on your roster')
    ).toBeInTheDocument();

    // Check available spots
    expect(screen.getByText('Available Roster Spots')).toBeInTheDocument();
    expect(screen.getByText(/You have 3 spots available/i)).toBeInTheDocument();

    // Check candidates
    expect(screen.getByText('Elite Stash 1')).toBeInTheDocument();
    expect(screen.getByText('High Upside 2')).toBeInTheDocument();
    expect(screen.getByText('Moderate Upside 3')).toBeInTheDocument();

    // Check reasoning
    expect(
      screen.getByText('Elite pitching prospect with ace potential')
    ).toBeInTheDocument();
    expect(
      screen.getByText('Power/speed combination with high ceiling')
    ).toBeInTheDocument();
  });

  it('should call fetchStashCandidates on mount when autoLoad is true', () => {
    const mockFetch = jest.fn();
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      fetchStashCandidates: mockFetch,
    });

    render(<StashCandidates leagueId={mockLeagueId} autoLoad={true} />);

    expect(mockFetch).toHaveBeenCalledWith(mockLeagueId);
  });

  it('should not call fetchStashCandidates on mount when autoLoad is false', () => {
    const mockFetch = jest.fn();
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      fetchStashCandidates: mockFetch,
    });

    render(<StashCandidates leagueId={mockLeagueId} autoLoad={false} />);

    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('should call fetchStashCandidates when refresh button is clicked', () => {
    const mockFetch = jest.fn();
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      stashCandidates: mockStashCandidates,
      fetchStashCandidates: mockFetch,
    });

    render(<StashCandidates leagueId={mockLeagueId} />);

    const refreshButton = screen.getByText('Refresh');
    fireEvent.click(refreshButton);

    expect(mockFetch).toHaveBeenCalledWith(mockLeagueId);
  });

  it('should call onProspectClick when candidate is clicked', () => {
    const mockOnClick = jest.fn();
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      stashCandidates: mockStashCandidates,
    });

    render(
      <StashCandidates leagueId={mockLeagueId} onProspectClick={mockOnClick} />
    );

    const candidate = screen.getByText('Elite Stash 1');
    fireEvent.click(candidate.closest('div')!);

    expect(mockOnClick).toHaveBeenCalledWith(1);
  });

  it('should call onRefresh callback when provided', () => {
    const mockOnRefresh = jest.fn();
    const mockFetch = jest.fn();
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      stashCandidates: mockStashCandidates,
      fetchStashCandidates: mockFetch,
    });

    render(
      <StashCandidates leagueId={mockLeagueId} onRefresh={mockOnRefresh} />
    );

    const refreshButton = screen.getByText('Refresh');
    fireEvent.click(refreshButton);

    expect(mockOnRefresh).toHaveBeenCalled();
  });

  it('should display correct upside labels', () => {
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      stashCandidates: mockStashCandidates,
    });

    render(<StashCandidates leagueId={mockLeagueId} />);

    // Check upside labels
    expect(screen.getByText('Elite Upside')).toBeInTheDocument();
    expect(screen.getByText('High Upside')).toBeInTheDocument();
    expect(screen.getByText('Moderate Upside')).toBeInTheDocument();
  });

  it('should display upside scores correctly', () => {
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      stashCandidates: mockStashCandidates,
    });

    render(<StashCandidates leagueId={mockLeagueId} />);

    // Check upside scores
    expect(screen.getByText('85')).toBeInTheDocument();
    expect(screen.getByText('70')).toBeInTheDocument();
    expect(screen.getByText('50')).toBeInTheDocument();
  });

  it('should display ETA years correctly', () => {
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      stashCandidates: mockStashCandidates,
    });

    render(<StashCandidates leagueId={mockLeagueId} />);

    // Check ETAs
    expect(screen.getByText('ETA: 2026')).toBeInTheDocument();
    expect(screen.getByText('ETA: 2025')).toBeInTheDocument();
    expect(screen.getByText('ETA: 2027')).toBeInTheDocument();
  });

  it('should handle zero available spots', () => {
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      stashCandidates: {
        available_spots: 0,
        stash_candidates: mockStashCandidates.stash_candidates,
      },
    });

    render(<StashCandidates leagueId={mockLeagueId} />);

    // Check for full roster message
    expect(
      screen.getByText('Your roster is currently full')
    ).toBeInTheDocument();

    // Check for roster management tip
    expect(screen.getByText(/Roster Management Tip/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Consider dropping underperforming veterans/i)
    ).toBeInTheDocument();
  });

  it('should handle one available spot (singular)', () => {
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      stashCandidates: {
        available_spots: 1,
        stash_candidates: mockStashCandidates.stash_candidates,
      },
    });

    render(<StashCandidates leagueId={mockLeagueId} />);

    // Check for singular spot message
    expect(screen.getByText(/You have 1 spot available/i)).toBeInTheDocument();
  });

  it('should display opportunity cost notice when spots and candidates available', () => {
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      stashCandidates: mockStashCandidates,
    });

    render(<StashCandidates leagueId={mockLeagueId} />);

    // Check for opportunity cost notice
    expect(screen.getByText(/Maximize your upside/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Consider your team's competitive window/i)
    ).toBeInTheDocument();
  });

  it('should not display opportunity cost notice when no spots available', () => {
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      stashCandidates: {
        available_spots: 0,
        stash_candidates: mockStashCandidates.stash_candidates,
      },
    });

    render(<StashCandidates leagueId={mockLeagueId} />);

    // Opportunity cost notice should not be visible
    expect(screen.queryByText(/Maximize your upside/i)).not.toBeInTheDocument();
  });

  it('should handle empty candidates list', () => {
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      stashCandidates: {
        available_spots: 2,
        stash_candidates: [],
      },
    });

    render(<StashCandidates leagueId={mockLeagueId} />);

    // Check for no candidates message
    expect(screen.getByText('No stash candidates found')).toBeInTheDocument();
    expect(
      screen.getByText(
        'Check back later for new high-upside prospects to stash'
      )
    ).toBeInTheDocument();
  });

  it('should display candidate count badge', () => {
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      stashCandidates: mockStashCandidates,
    });

    render(<StashCandidates leagueId={mockLeagueId} />);

    // Check for recommended targets header
    expect(screen.getByText('Recommended Stash Targets')).toBeInTheDocument();

    // Check for count badge - text "3" appears multiple times (available spots, badge count, upside scores)
    const badges = screen.getAllByText('3');
    expect(badges.length).toBeGreaterThan(0);
  });

  it('should handle speculative upside score', () => {
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      stashCandidates: {
        available_spots: 1,
        stash_candidates: [
          {
            prospect_id: 99,
            name: 'Speculative Prospect',
            position: 'RP',
            upside_score: 30,
            eta: '2028',
            reasoning: 'Very raw but high ceiling if everything clicks',
          },
        ],
      },
    });

    render(<StashCandidates leagueId={mockLeagueId} />);

    // Check for speculative label
    expect(screen.getByText('Speculative')).toBeInTheDocument();
    expect(screen.getByText('30')).toBeInTheDocument();
  });
});
