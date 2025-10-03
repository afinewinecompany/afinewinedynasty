/**
 * @jest-environment jsdom
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { TeamNeedsOverview } from '@/components/recommendations/TeamNeedsOverview';
import { useRecommendations } from '@/hooks/useRecommendations';
import type { TeamNeeds } from '@/types/recommendations';

// Mock the hook
jest.mock('@/hooks/useRecommendations');

const mockUseRecommendations = useRecommendations as jest.MockedFunction<
  typeof useRecommendations
>;

describe('TeamNeedsOverview Component', () => {
  const mockLeagueId = 'test-league-123';

  const mockTeamNeeds: TeamNeeds = {
    positional_needs: [
      { position: 'SP', severity: 'critical', timeline: 'immediate' },
      { position: 'OF', severity: 'medium', timeline: 'near_term' },
    ],
    depth_analysis: {
      SP: { starters: 2, depth: 1, gap_score: 75 },
      OF: { starters: 3, depth: 2, gap_score: 40 },
    },
    competitive_window: 'contending',
    future_needs: {
      '2_year': ['C', '2B'],
      '3_year': ['SS'],
    },
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
      loading: { ...defaultMockReturn.loading, teamNeeds: true },
    });

    render(<TeamNeedsOverview leagueId={mockLeagueId} />);

    expect(screen.getByText('Analyzing team needs...')).toBeInTheDocument();
  });

  it('should render error state', () => {
    const errorMessage = 'Failed to load team needs';
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      error: { ...defaultMockReturn.error, teamNeeds: errorMessage },
    });

    render(<TeamNeedsOverview leagueId={mockLeagueId} />);

    expect(screen.getByText(errorMessage)).toBeInTheDocument();
    expect(screen.getByText('Try Again')).toBeInTheDocument();
  });

  it('should render empty state when no data', () => {
    render(<TeamNeedsOverview leagueId={mockLeagueId} autoLoad={false} />);

    expect(screen.getByText('No team analysis available')).toBeInTheDocument();
    expect(screen.getByText('Load Team Needs')).toBeInTheDocument();
  });

  it('should display team needs data correctly', () => {
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      teamNeeds: mockTeamNeeds,
    });

    render(<TeamNeedsOverview leagueId={mockLeagueId} />);

    // Check title
    expect(screen.getByText('Team Needs Overview')).toBeInTheDocument();

    // Check competitive window
    expect(screen.getByText('Contending')).toBeInTheDocument();

    // Check positional needs (using getAllByText since positions appear multiple times)
    expect(screen.getAllByText('SP').length).toBeGreaterThan(0);
    expect(screen.getAllByText('OF').length).toBeGreaterThan(0);
    expect(screen.getByText('critical')).toBeInTheDocument();
    expect(screen.getByText('medium')).toBeInTheDocument();

    // Check depth analysis
    expect(screen.getByText('Depth Chart Analysis')).toBeInTheDocument();

    // Check future needs
    expect(screen.getByText('2-Year Outlook')).toBeInTheDocument();
    expect(screen.getByText('3-Year Outlook')).toBeInTheDocument();
    expect(screen.getByText('C')).toBeInTheDocument();
    expect(screen.getByText('2B')).toBeInTheDocument();
  });

  it('should call fetchTeamNeeds on mount when autoLoad is true', () => {
    const mockFetch = jest.fn();
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      fetchTeamNeeds: mockFetch,
    });

    render(<TeamNeedsOverview leagueId={mockLeagueId} autoLoad={true} />);

    expect(mockFetch).toHaveBeenCalledWith(mockLeagueId);
  });

  it('should not call fetchTeamNeeds on mount when autoLoad is false', () => {
    const mockFetch = jest.fn();
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      fetchTeamNeeds: mockFetch,
    });

    render(<TeamNeedsOverview leagueId={mockLeagueId} autoLoad={false} />);

    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('should call fetchTeamNeeds when refresh button is clicked', () => {
    const mockFetch = jest.fn();
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      teamNeeds: mockTeamNeeds,
      fetchTeamNeeds: mockFetch,
    });

    render(<TeamNeedsOverview leagueId={mockLeagueId} />);

    const refreshButton = screen.getByText('Refresh');
    fireEvent.click(refreshButton);

    expect(mockFetch).toHaveBeenCalledWith(mockLeagueId);
  });

  it('should call onRefresh callback when provided', () => {
    const mockOnRefresh = jest.fn();
    const mockFetch = jest.fn();
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      teamNeeds: mockTeamNeeds,
      fetchTeamNeeds: mockFetch,
    });

    render(
      <TeamNeedsOverview leagueId={mockLeagueId} onRefresh={mockOnRefresh} />
    );

    const refreshButton = screen.getByText('Refresh');
    fireEvent.click(refreshButton);

    expect(mockOnRefresh).toHaveBeenCalled();
  });

  it('should display correct severity colors', () => {
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      teamNeeds: mockTeamNeeds,
    });

    const { container } = render(<TeamNeedsOverview leagueId={mockLeagueId} />);

    // Critical should have red styling
    const criticalBadge = screen.getByText('critical');
    expect(criticalBadge).toHaveClass('bg-red-100', 'text-red-800');

    // Medium should have yellow styling
    const mediumBadge = screen.getByText('medium');
    expect(mediumBadge).toHaveClass('bg-yellow-100', 'text-yellow-800');
  });

  it('should handle rebuilding competitive window', () => {
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      teamNeeds: {
        ...mockTeamNeeds,
        competitive_window: 'rebuilding',
      },
    });

    render(<TeamNeedsOverview leagueId={mockLeagueId} />);

    expect(screen.getByText('Rebuilding')).toBeInTheDocument();
    expect(
      screen.getByText(
        /Your team is rebuilding. Prioritize high-upside prospects/i
      )
    ).toBeInTheDocument();
  });
});
