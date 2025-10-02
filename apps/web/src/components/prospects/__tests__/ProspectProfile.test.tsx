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

// Mock the new components
jest.mock('../MLPredictionExplanation', () => {
  return {
    MLPredictionExplanation: ({ prediction, prospectName }: any) => (
      <div data-testid="ml-prediction-explanation">
        <div>ML Analysis for {prospectName}</div>
        <div>
          Probability: {(prediction.success_probability * 100).toFixed(1)}%
        </div>
        <div>Confidence: {prediction.confidence_level}</div>
      </div>
    ),
  };
});

jest.mock('../ScoutingRadar', () => {
  return {
    ScoutingRadar: ({ scoutingGrades, prospectName }: any) => (
      <div data-testid="scouting-radar">
        <div>Scouting for {prospectName}</div>
        <div>Grades: {scoutingGrades.length} sources</div>
      </div>
    ),
  };
});

jest.mock('../PerformanceTrends', () => {
  return {
    PerformanceTrends: ({ prospectName, position }: any) => (
      <div data-testid="performance-trends">
        <div>Performance trends for {prospectName}</div>
        <div>Position: {position}</div>
      </div>
    ),
  };
});

jest.mock('@/components/ui/SocialShare', () => {
  return {
    SocialShare: ({ title, url }: any) => (
      <div data-testid="social-share">
        <div>Share: {title}</div>
        <div>URL: {url}</div>
      </div>
    ),
  };
});

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
  dynasty_rank: 15,
  dynasty_score: 87.5,
  ml_score: 82.3,
  scouting_score: 75.8,
  confidence_level: 'High' as const,
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
      batting_avg: 0.3,
      on_base_pct: 0.38,
      slugging_pct: 0.52,
      woba: 0.365,
      wrc_plus: 125,
    },
  ],
  ml_prediction: {
    prospect_id: '1',
    success_probability: 0.75,
    confidence_level: 'High' as const,
    prediction_date: '2024-01-01T00:00:00Z',
    shap_explanation: {
      top_positive_features: [
        { feature: 'batting_avg', shap_value: 0.12, feature_value: 0.3 },
        { feature: 'age', shap_value: 0.08, feature_value: 22 },
      ],
      top_negative_features: [
        { feature: 'strikeout_rate', shap_value: -0.05, feature_value: 22.5 },
      ],
      expected_value: 0.45,
      total_shap_contribution: 0.3,
      prediction_score: 0.75,
    },
    narrative: 'Strong offensive profile with good plate discipline',
    model_version: 'v2.1.0',
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
    expect(
      screen.getByText('Failed to fetch prospect profile')
    ).toBeInTheDocument();

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
    expect(
      screen.getByText('Strong offensive profile with good plate discipline')
    ).toBeInTheDocument();
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

    expect(
      screen.getByText('No prediction data available')
    ).toBeInTheDocument();
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

  // Enhanced feature tests
  it('renders enhanced ML prediction explanation', () => {
    render(<ProspectProfile id="1" />);

    const mlExplanation = screen.getByTestId('ml-prediction-explanation');
    expect(mlExplanation).toBeInTheDocument();
    expect(screen.getByText('ML Analysis for John Smith')).toBeInTheDocument();
    expect(screen.getByText('Probability: 75.0%')).toBeInTheDocument();
    expect(screen.getByText('Confidence: High')).toBeInTheDocument();
  });

  it('renders dynasty metrics card correctly', () => {
    render(<ProspectProfile id="1" />);

    expect(screen.getByText('Dynasty Metrics')).toBeInTheDocument();
    expect(screen.getByText('87.5')).toBeInTheDocument(); // Dynasty score
    expect(screen.getByText('82.3')).toBeInTheDocument(); // ML score
    expect(screen.getByText('75.8')).toBeInTheDocument(); // Scouting score
    expect(screen.getByText('#15')).toBeInTheDocument(); // Dynasty rank
  });

  it('renders social sharing component', () => {
    render(<ProspectProfile id="1" />);

    const socialShare = screen.getByTestId('social-share');
    expect(socialShare).toBeInTheDocument();
    expect(
      screen.getByText('Share: John Smith - SS Prospect Profile')
    ).toBeInTheDocument();
    expect(screen.getByText('URL: /prospects/1')).toBeInTheDocument();
  });

  it('renders quick actions correctly', () => {
    render(<ProspectProfile id="1" />);

    expect(screen.getByText('Add to Watchlist')).toBeInTheDocument();
    expect(screen.getByText('View on MLB.com')).toBeInTheDocument();
    expect(screen.getByText('Compare Players')).toBeInTheDocument();
  });

  it('handles enhanced scouting tab', () => {
    render(<ProspectProfile id="1" />);

    const scoutingTab = screen.getByRole('button', { name: /scouting/i });
    fireEvent.click(scoutingTab);

    const scoutingRadar = screen.getByTestId('scouting-radar');
    expect(scoutingRadar).toBeInTheDocument();
    expect(screen.getByText('Scouting for John Smith')).toBeInTheDocument();
  });

  it('handles enhanced statistics tab with performance trends', () => {
    render(<ProspectProfile id="1" />);

    const statisticsTab = screen.getByRole('button', { name: /statistics/i });
    fireEvent.click(statisticsTab);

    expect(screen.getByText('Current Season Summary')).toBeInTheDocument();

    const performanceTrends = screen.getByTestId('performance-trends');
    expect(performanceTrends).toBeInTheDocument();
    expect(
      screen.getByText('Performance trends for John Smith')
    ).toBeInTheDocument();
    expect(screen.getByText('Position: SS')).toBeInTheDocument();
  });

  it('handles comparisons tab', () => {
    render(<ProspectProfile id="1" />);

    const comparisonsTab = screen.getByRole('button', { name: /comparisons/i });
    fireEvent.click(comparisonsTab);

    expect(
      screen.getByText('Current Prospect Comparisons')
    ).toBeInTheDocument();
    expect(screen.getByText('Historical MLB Comparisons')).toBeInTheDocument();
  });

  it('handles history tab', () => {
    render(<ProspectProfile id="1" />);

    const historyTab = screen.getByRole('button', { name: /history/i });
    fireEvent.click(historyTab);

    expect(screen.getByText('Career Timeline')).toBeInTheDocument();
    expect(screen.getByText('Injury History')).toBeInTheDocument();
    expect(screen.getByText('Development Notes')).toBeInTheDocument();
  });

  it('displays all available tabs', () => {
    render(<ProspectProfile id="1" />);

    expect(
      screen.getByRole('button', { name: /overview/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /statistics/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /scouting/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /comparisons/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /history/i })
    ).toBeInTheDocument();
  });

  it('maintains responsive layout structure', () => {
    render(<ProspectProfile id="1" />);

    // Check that the grid layout exists
    const gridLayout = screen.getByText('Dynasty Metrics').closest('.grid');
    expect(gridLayout).toHaveClass('grid-cols-1', 'lg:grid-cols-3');
  });

  it('handles confidence level badge variants correctly', () => {
    render(<ProspectProfile id="1" />);

    const confidenceBadge = screen.getByText('High Confidence');
    expect(confidenceBadge.closest('.inline-flex')).toHaveClass('inline-flex');
  });

  it('renders dynasty rank badge correctly', () => {
    render(<ProspectProfile id="1" />);

    const rankBadge = screen.getByText('#15');
    expect(rankBadge).toBeInTheDocument();
  });

  it('handles prospect without dynasty metrics gracefully', () => {
    (useProspectProfile as jest.Mock).mockReturnValue({
      data: {
        ...mockProspectData,
        dynasty_score: undefined,
        ml_score: undefined,
        scouting_score: undefined,
        confidence_level: undefined,
      },
      loading: false,
      error: null,
      refetch: jest.fn(),
    });

    render(<ProspectProfile id="1" />);

    expect(screen.getByText('Dynasty Metrics')).toBeInTheDocument();
    expect(screen.getByText('N/A')).toBeInTheDocument();
  });

  it('handles medium and low confidence levels', () => {
    (useProspectProfile as jest.Mock).mockReturnValue({
      data: { ...mockProspectData, confidence_level: 'Medium' },
      loading: false,
      error: null,
      refetch: jest.fn(),
    });

    render(<ProspectProfile id="1" />);

    const mediumBadge = screen.getByText('Medium Confidence');
    expect(mediumBadge).toBeInTheDocument();
  });

  it('displays current season summary with OPS calculation', () => {
    render(<ProspectProfile id="1" />);

    const statisticsTab = screen.getByRole('button', { name: /statistics/i });
    fireEvent.click(statisticsTab);

    expect(screen.getByText('0.900')).toBeInTheDocument(); // OPS = OBP + SLG
  });

  it('passes correct props to PerformanceTrends component', () => {
    render(<ProspectProfile id="1" />);

    const statisticsTab = screen.getByRole('button', { name: /statistics/i });
    fireEvent.click(statisticsTab);

    const performanceTrends = screen.getByTestId('performance-trends');
    expect(performanceTrends).toBeInTheDocument();
    // Props are verified in the mock component
  });

  it('handles empty stats array for enhanced statistics', () => {
    (useProspectProfile as jest.Mock).mockReturnValue({
      data: { ...mockProspectData, stats: [] },
      loading: false,
      error: null,
      refetch: jest.fn(),
    });

    render(<ProspectProfile id="1" />);

    const statisticsTab = screen.getByRole('button', { name: /statistics/i });
    fireEvent.click(statisticsTab);

    expect(screen.getByText('No statistics available')).toBeInTheDocument();
  });
});
