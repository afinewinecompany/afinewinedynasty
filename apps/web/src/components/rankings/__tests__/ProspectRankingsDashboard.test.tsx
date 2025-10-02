import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import ProspectRankingsDashboard from '../ProspectRankingsDashboard';
import { useProspectRankings } from '@/hooks/useProspectRankings';
import { useProspectSearch } from '@/hooks/useProspectSearch';
import { useAuth } from '@/hooks/useAuth';

// Mock hooks
jest.mock('@/hooks/useProspectRankings');
jest.mock('@/hooks/useProspectSearch');
jest.mock('@/hooks/useAuth');
jest.mock('@/lib/api/prospects');

const mockProspectData = {
  prospects: [
    {
      id: 1,
      mlbId: '123456',
      name: 'Test Player',
      position: 'SS',
      organization: 'Test Team',
      level: 'Double-A',
      age: 22,
      etaYear: 2025,
      dynastyRank: 1,
      dynastyScore: 85.5,
      mlScore: 30.2,
      scoutingScore: 22.5,
      confidenceLevel: 'High',
      battingAvg: 0.285,
      onBasePct: 0.36,
      sluggingPct: 0.45,
      futureValue: 55,
    },
    {
      id: 2,
      mlbId: '789012',
      name: 'Another Player',
      position: 'SP',
      organization: 'Another Team',
      level: 'Triple-A',
      age: 23,
      etaYear: 2024,
      dynastyRank: 2,
      dynastyScore: 82.0,
      mlScore: 28.5,
      scoutingScore: 20.0,
      confidenceLevel: 'Medium',
      era: 3.25,
      whip: 1.15,
      futureValue: 50,
    },
  ],
  total: 100,
  page: 1,
  pageSize: 50,
  totalPages: 2,
};

describe('ProspectRankingsDashboard', () => {
  beforeEach(() => {
    // Reset mocks
    jest.clearAllMocks();

    // Default mock implementations
    (useProspectRankings as jest.Mock).mockReturnValue({
      data: mockProspectData,
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    });

    (useProspectSearch as jest.Mock).mockReturnValue({
      suggestions: [],
      getSuggestions: jest.fn(),
    });

    (useAuth as jest.Mock).mockReturnValue({
      user: { id: 1, email: 'test@example.com', subscriptionTier: 'free' },
    });
  });

  it('renders the dashboard header correctly', () => {
    render(<ProspectRankingsDashboard />);

    expect(screen.getByText('Prospect Rankings')).toBeInTheDocument();
    expect(screen.getByText(/Top 500 dynasty prospects/)).toBeInTheDocument();
  });

  it('displays loading state', () => {
    (useProspectRankings as jest.Mock).mockReturnValue({
      data: null,
      isLoading: true,
      error: null,
      refetch: jest.fn(),
    });

    const { container } = render(<ProspectRankingsDashboard />);

    expect(container.querySelector('.animate-spin')).toBeInTheDocument();
  });

  it('displays error state and retry button', () => {
    const refetchMock = jest.fn();
    (useProspectRankings as jest.Mock).mockReturnValue({
      data: null,
      isLoading: false,
      error: new Error('Failed to load'),
      refetch: refetchMock,
    });

    render(<ProspectRankingsDashboard />);

    expect(screen.getByText(/Failed to load rankings/)).toBeInTheDocument();

    const retryButton = screen.getByText('Retry');
    fireEvent.click(retryButton);
    expect(refetchMock).toHaveBeenCalled();
  });

  it('renders prospect data in table format', () => {
    render(<ProspectRankingsDashboard />);

    expect(screen.getByText('Test Player')).toBeInTheDocument();
    expect(screen.getByText('Another Player')).toBeInTheDocument();
    expect(screen.getByText('SS')).toBeInTheDocument();
    expect(screen.getByText('SP')).toBeInTheDocument();
  });

  it('handles search functionality', () => {
    const getSuggestionsMock = jest.fn();
    (useProspectSearch as jest.Mock).mockReturnValue({
      suggestions: [
        {
          name: 'Juan Soto',
          organization: 'San Diego Padres',
          position: 'RF',
          display: 'Juan Soto (RF, San Diego Padres)',
        },
      ],
      getSuggestions: getSuggestionsMock,
    });

    render(<ProspectRankingsDashboard />);

    const searchInput = screen.getByPlaceholderText(/Search prospects/);
    fireEvent.change(searchInput, { target: { value: 'Juan' } });

    expect(getSuggestionsMock).toHaveBeenCalledWith('Juan');
  });

  it('shows export button for premium users only', () => {
    // Test with free user
    render(<ProspectRankingsDashboard />);
    expect(screen.queryByText('Export CSV')).not.toBeInTheDocument();

    // Test with premium user
    (useAuth as jest.Mock).mockReturnValue({
      user: {
        id: 1,
        email: 'premium@example.com',
        subscriptionTier: 'premium',
      },
    });

    render(<ProspectRankingsDashboard />);
    expect(screen.getByText('Export CSV')).toBeInTheDocument();
  });

  it('displays active filters indicator', () => {
    (useProspectRankings as jest.Mock).mockReturnValue({
      data: mockProspectData,
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    });

    const { rerender } = render(<ProspectRankingsDashboard />);

    // Initially no active filters
    expect(screen.queryByText(/Active Filters/)).not.toBeInTheDocument();

    // Add a search query
    const searchInput = screen.getByPlaceholderText(/Search prospects/);
    fireEvent.change(searchInput, { target: { value: 'Test' } });

    // Trigger re-render with search
    rerender(<ProspectRankingsDashboard />);

    waitFor(() => {
      expect(screen.getByText(/results/)).toBeInTheDocument();
    });
  });

  it('handles pagination controls', () => {
    render(<ProspectRankingsDashboard />);

    expect(screen.getByText(/Showing.*1.*to.*50.*of.*100/)).toBeInTheDocument();

    // Check page size selector
    const pageSizeSelector = screen.getByLabelText('Show:');
    expect(pageSizeSelector).toHaveValue('50');

    fireEvent.change(pageSizeSelector, { target: { value: '25' } });
    expect(pageSizeSelector).toHaveValue('25');
  });

  it('handles empty results', () => {
    (useProspectRankings as jest.Mock).mockReturnValue({
      data: {
        prospects: [],
        total: 0,
        page: 1,
        pageSize: 50,
        totalPages: 0,
      },
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    });

    render(<ProspectRankingsDashboard />);

    expect(
      screen.getByText(/No prospects found matching your criteria/)
    ).toBeInTheDocument();
  });
});
