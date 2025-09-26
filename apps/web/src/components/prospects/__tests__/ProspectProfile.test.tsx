import { render, screen, fireEvent } from '@testing-library/react';
import { useRouter } from 'next/navigation';
import ProspectProfile from '../ProspectProfile';
import { useProspectProfile } from '@/hooks/useProspectProfile';

// Mock Next.js navigation
jest.mock('next/navigation', () => ({
  useRouter: jest.fn(),
}));

// Mock the useProspectProfile hook
jest.mock('@/hooks/useProspectProfile');

const mockRouter = {
  push: jest.fn(),
  replace: jest.fn(),
  back: jest.fn(),
};

const mockProspectData = {
  id: '1',
  mlb_id: 'mlb1',
  name: 'John Smith',
  position: 'SS',
  organization: 'New York Yankees',
  level: 'AAA',
  age: 22,
  eta_year: 2025,
  scouting_grade: 85,
  stats: [
    {
      prospect_id: '1',
      timestamp: '2024-01-01T00:00:00Z',
      games_played: 50,
      at_bats: 200,
      hits: 60,
      home_runs: 12,
      rbi: 45,
      batting_avg: 0.300,
      on_base_pct: 0.380,
      slugging_pct: 0.520,
      woba: 0.365,
      wrc_plus: 125,
    },
  ],
  ml_prediction: {
    prospect_id: '1',
    success_probability: 0.75,
    confidence_level: 'High' as const,
    explanation: 'Strong offensive profile with good plate discipline',
    generated_at: '2024-01-01T00:00:00Z',
  },
};

describe('ProspectProfile', () => {
  beforeEach(() => {
    (useRouter as jest.Mock).mockReturnValue(mockRouter);
    (useProspectProfile as jest.Mock).mockReturnValue({
      data: mockProspectData,
      loading: false,
      error: null,
      refetch: jest.fn(),
    });
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it('renders prospect header correctly', () => {
    render(<ProspectProfile id="1" />);

    expect(screen.getAllByText('John Smith')).toHaveLength(2); // Once in breadcrumb, once in header
    expect(screen.getAllByText('SS')).toHaveLength(2); // Once in header, once in basic info
    expect(screen.getAllByText('New York Yankees')).toHaveLength(2); // Once in header, once in basic info
    expect(screen.getAllByText('AAA')).toHaveLength(2); // Once in header, once in basic info
    expect(screen.getByText('Age 22')).toBeInTheDocument();
    expect(screen.getByText('ETA 2025')).toBeInTheDocument();
  });

  it('renders breadcrumb navigation', () => {
    render(<ProspectProfile id="1" />);

    expect(screen.getByText('Prospect Rankings')).toBeInTheDocument();
    expect(screen.getAllByText('John Smith')).toHaveLength(2); // Once in breadcrumb, once in header
  });

  it('displays loading state correctly', () => {
    (useProspectProfile as jest.Mock).mockReturnValue({
      data: null,
      loading: true,
      error: null,
      refetch: jest.fn(),
    });

    render(<ProspectProfile id="1" />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('displays error state correctly', () => {
    const mockRefetch = jest.fn();
    (useProspectProfile as jest.Mock).mockReturnValue({
      data: null,
      loading: false,
      error: 'Failed to fetch prospect profile',
      refetch: mockRefetch,
    });

    render(<ProspectProfile id="1" />);
    expect(screen.getByText('Failed to fetch prospect profile')).toBeInTheDocument();

    const retryButton = screen.getByText('Try Again');
    fireEvent.click(retryButton);
    expect(mockRefetch).toHaveBeenCalledTimes(1);
  });

  it('displays not found state correctly', () => {
    (useProspectProfile as jest.Mock).mockReturnValue({
      data: null,
      loading: false,
      error: null,
      refetch: jest.fn(),
    });

    render(<ProspectProfile id="1" />);
    expect(screen.getByText('Prospect not found')).toBeInTheDocument();
    expect(screen.getByText('Back to Rankings')).toBeInTheDocument();
  });

  it('renders ML prediction card correctly', () => {
    render(<ProspectProfile id="1" />);

    expect(screen.getByText('ML Prediction')).toBeInTheDocument();
    expect(screen.getByText('75%')).toBeInTheDocument();
    expect(screen.getByText('High')).toBeInTheDocument();
    expect(screen.getByText('Strong offensive profile with good plate discipline')).toBeInTheDocument();
  });

  it('renders basic information correctly', () => {
    render(<ProspectProfile id="1" />);

    expect(screen.getByText('Basic Information')).toBeInTheDocument();
    expect(screen.getByText('Position')).toBeInTheDocument();
    expect(screen.getByText('Organization')).toBeInTheDocument();
    expect(screen.getByText('Level')).toBeInTheDocument();
    expect(screen.getByText('Age')).toBeInTheDocument();
    expect(screen.getByText('ETA Year')).toBeInTheDocument();
    expect(screen.getByText('Scouting Grade')).toBeInTheDocument();
    expect(screen.getByText('85/100')).toBeInTheDocument();
  });

  it('handles tab switching correctly', () => {
    render(<ProspectProfile id="1" />);

    // Default tab should be Overview
    expect(screen.getByText('Basic Information')).toBeInTheDocument();

    // Click on Statistics tab
    const statisticsTab = screen.getByRole('button', { name: /statistics/i });
    fireEvent.click(statisticsTab);

    expect(screen.getByText('Hitting Statistics')).toBeInTheDocument();
    expect(screen.getByText('Advanced Metrics')).toBeInTheDocument();

    // Click on Scouting tab
    const scoutingTab = screen.getByRole('button', { name: /scouting/i });
    fireEvent.click(scoutingTab);

    expect(screen.getByText('Scouting report coming soon')).toBeInTheDocument();
  });

  it('displays hitting statistics correctly', () => {
    render(<ProspectProfile id="1" />);

    // Go to Statistics tab
    const statisticsTab = screen.getByRole('button', { name: /statistics/i });
    fireEvent.click(statisticsTab);

    expect(screen.getByText('50')).toBeInTheDocument(); // Games
    expect(screen.getByText('200')).toBeInTheDocument(); // At Bats
    expect(screen.getByText('60')).toBeInTheDocument(); // Hits
    expect(screen.getByText('12')).toBeInTheDocument(); // Home Runs
    expect(screen.getByText('45')).toBeInTheDocument(); // RBI
    expect(screen.getByText('0.300')).toBeInTheDocument(); // AVG
    expect(screen.getByText('0.380')).toBeInTheDocument(); // OBP
    expect(screen.getByText('0.520')).toBeInTheDocument(); // SLG
  });

  it('displays advanced metrics correctly', () => {
    render(<ProspectProfile id="1" />);

    // Go to Statistics tab
    const statisticsTab = screen.getByRole('button', { name: /statistics/i });
    fireEvent.click(statisticsTab);

    expect(screen.getByText('0.365')).toBeInTheDocument(); // wOBA
    expect(screen.getByText('125')).toBeInTheDocument(); // wRC+
  });

  it('handles prospect without stats gracefully', () => {
    (useProspectProfile as jest.Mock).mockReturnValue({
      data: { ...mockProspectData, stats: [] },
      loading: false,
      error: null,
      refetch: jest.fn(),
    });

    render(<ProspectProfile id="1" />);

    // Go to Statistics tab
    const statisticsTab = screen.getByRole('button', { name: /statistics/i });
    fireEvent.click(statisticsTab);

    expect(screen.getByText('No statistics available')).toBeInTheDocument();
  });

  it('handles prospect without ML prediction gracefully', () => {
    (useProspectProfile as jest.Mock).mockReturnValue({
      data: { ...mockProspectData, ml_prediction: undefined },
      loading: false,
      error: null,
      refetch: jest.fn(),
    });

    render(<ProspectProfile id="1" />);

    expect(screen.getByText('No prediction data available')).toBeInTheDocument();
  });

  it('renders tabs with correct counts', () => {
    render(<ProspectProfile id="1" />);

    const statisticsTab = screen.getByRole('button', { name: /statistics/i });
    expect(statisticsTab).toHaveTextContent('1'); // One stats entry
  });

  it('displays ML prediction confidence colors correctly', () => {
    render(<ProspectProfile id="1" />);

    // High confidence should have green styling
    const confidenceBadge = screen.getByText('High');
    expect(confidenceBadge).toHaveClass('bg-green-100', 'text-green-800');
  });

  it('formats dates correctly', () => {
    render(<ProspectProfile id="1" />);

    expect(screen.getByText(/Generated on/)).toBeInTheDocument();
  });
});