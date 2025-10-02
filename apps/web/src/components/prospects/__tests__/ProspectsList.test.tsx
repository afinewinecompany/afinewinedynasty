import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { useRouter, useSearchParams } from 'next/navigation';
import ProspectsList from '../ProspectsList';
import { useProspects } from '@/hooks/useProspects';

// Mock Next.js navigation
jest.mock('next/navigation', () => ({
  useRouter: jest.fn(),
  useSearchParams: jest.fn(),
}));

// Mock the useProspects hook
jest.mock('@/hooks/useProspects');

// Mock ResizeObserver for responsive testing
global.ResizeObserver = jest.fn().mockImplementation(() => ({
  observe: jest.fn(),
  unobserve: jest.fn(),
  disconnect: jest.fn(),
}));

// Mock window.matchMedia for mobile responsiveness
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: jest.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: jest.fn(),
    removeListener: jest.fn(),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
  })),
});

const mockRouter = {
  push: jest.fn(),
  replace: jest.fn(),
  back: jest.fn(),
  forward: jest.fn(),
  refresh: jest.fn(),
};

const mockSearchParams = new URLSearchParams();

const mockProspectsData = {
  prospects: [
    {
      id: '1',
      mlb_id: 'mlb1',
      name: 'John Smith',
      position: 'SS',
      organization: 'New York Yankees',
      level: 'AAA',
      age: 22,
      eta_year: 2025,
    },
    {
      id: '2',
      mlb_id: 'mlb2',
      name: 'Mike Johnson',
      position: 'OF',
      organization: 'Boston Red Sox',
      level: 'AA',
      age: 20,
      eta_year: 2026,
    },
  ],
  total: 100,
  page: 1,
  limit: 25,
  total_pages: 4,
};

describe('ProspectsList', () => {
  beforeEach(() => {
    (useRouter as jest.Mock).mockReturnValue(mockRouter);
    (useSearchParams as jest.Mock).mockReturnValue(mockSearchParams);
    (useProspects as jest.Mock).mockReturnValue({
      data: mockProspectsData,
      loading: false,
      error: null,
      refetch: jest.fn(),
    });
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it('renders the prospect rankings title', () => {
    render(<ProspectsList />);
    expect(screen.getByText('Prospect Rankings')).toBeInTheDocument();
    expect(
      screen.getByText('Top 100 MLB prospects with detailed stats and analysis')
    ).toBeInTheDocument();
  });

  it('renders prospects in table format on desktop', () => {
    render(<ProspectsList />);

    expect(screen.getByText('John Smith')).toBeInTheDocument();
    expect(screen.getByText('Mike Johnson')).toBeInTheDocument();

    // Use getAllByText to handle multiple instances of team names
    const yankees = screen.getAllByText('New York Yankees');
    expect(yankees.length).toBeGreaterThan(0);

    const redSox = screen.getAllByText('Boston Red Sox');
    expect(redSox.length).toBeGreaterThan(0);
  });

  it('displays loading state correctly', () => {
    (useProspects as jest.Mock).mockReturnValue({
      data: null,
      loading: true,
      error: null,
      refetch: jest.fn(),
    });

    render(<ProspectsList />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('displays error state correctly', () => {
    const mockRefetch = jest.fn();
    (useProspects as jest.Mock).mockReturnValue({
      data: null,
      loading: false,
      error: 'Failed to fetch prospects',
      refetch: mockRefetch,
    });

    render(<ProspectsList />);
    expect(screen.getByText('Failed to fetch prospects')).toBeInTheDocument();

    const retryButton = screen.getByText('Try Again');
    fireEvent.click(retryButton);
    expect(mockRefetch).toHaveBeenCalledTimes(1);
  });

  it('handles search input correctly', async () => {
    render(<ProspectsList />);

    const searchInput = screen.getByPlaceholderText(
      'Search prospects by name...'
    );
    fireEvent.change(searchInput, { target: { value: 'John' } });

    expect(searchInput).toHaveValue('John');

    // Test debounced search
    await waitFor(
      () => {
        expect(useProspects).toHaveBeenCalledWith(
          expect.objectContaining({
            search: 'John',
            page: 1,
          })
        );
      },
      { timeout: 500 }
    );
  });

  it('handles filter changes correctly', () => {
    // Force desktop view
    Object.defineProperty(window, 'innerWidth', {
      writable: true,
      configurable: true,
      value: 1024,
    });

    render(<ProspectsList />);

    // Test position filter - target the desktop position selector
    const positionSelect = screen.getByLabelText('Position');
    fireEvent.change(positionSelect, { target: { value: 'SS' } });

    expect(useProspects).toHaveBeenCalledWith(
      expect.objectContaining({
        position: 'SS',
        page: 1,
      })
    );
  });

  it('handles sorting correctly', () => {
    render(<ProspectsList />);

    const nameHeader = screen.getByText('Name').closest('th');
    fireEvent.click(nameHeader!);

    expect(useProspects).toHaveBeenCalledWith(
      expect.objectContaining({
        sort_by: 'name',
        sort_order: 'desc',
        page: 1,
      })
    );
  });

  it('handles pagination correctly', () => {
    render(<ProspectsList />);

    // Use getAllByText to handle multiple "Next" instances and pick the first (visible button)
    const nextButtons = screen.getAllByText('Next');
    const nextButton = nextButtons[0]; // The visible button
    fireEvent.click(nextButton);

    expect(useProspects).toHaveBeenCalledWith(
      expect.objectContaining({
        page: 2,
      })
    );
  });

  it('displays no results message when prospects array is empty', () => {
    (useProspects as jest.Mock).mockReturnValue({
      data: { ...mockProspectsData, prospects: [] },
      loading: false,
      error: null,
      refetch: jest.fn(),
    });

    render(<ProspectsList />);
    expect(screen.getByText('No prospects found')).toBeInTheDocument();
    expect(
      screen.getByText('Try adjusting your search or filter criteria.')
    ).toBeInTheDocument();
  });

  it('renders mobile view correctly', () => {
    // Mock mobile viewport
    Object.defineProperty(window, 'innerWidth', {
      writable: true,
      configurable: true,
      value: 500,
    });

    render(<ProspectsList />);

    // Should have mobile filters button instead of sidebar
    expect(screen.getByText('Filters')).toBeInTheDocument();
  });

  it('handles clear filters correctly', () => {
    // Force desktop view by mocking window.innerWidth
    Object.defineProperty(window, 'innerWidth', {
      writable: true,
      configurable: true,
      value: 1024,
    });

    render(<ProspectsList />);

    // First set some filters - target the desktop filter panel select
    const positionSelect = screen.getByLabelText('Position');
    fireEvent.change(positionSelect, { target: { value: 'SS' } });

    // Then clear them
    const clearButton = screen.getByText('Clear Filters');
    fireEvent.click(clearButton);

    expect(useProspects).toHaveBeenCalledWith(
      expect.objectContaining({
        position: '',
        organization: '',
        page: 1,
      })
    );
  });

  it('performance: renders large prospect lists efficiently', () => {
    const largeProspectsList = {
      ...mockProspectsData,
      prospects: Array.from({ length: 25 }, (_, i) => ({
        id: `${i + 1}`,
        mlb_id: `mlb${i + 1}`,
        name: `Prospect ${i + 1}`,
        position: 'OF',
        organization: 'Team',
        level: 'AAA',
        age: 20,
        eta_year: 2025,
      })),
    };

    (useProspects as jest.Mock).mockReturnValue({
      data: largeProspectsList,
      loading: false,
      error: null,
      refetch: jest.fn(),
    });

    const startTime = performance.now();
    render(<ProspectsList />);
    const endTime = performance.now();

    // Should render in under 1 second
    expect(endTime - startTime).toBeLessThan(1000);

    // Should display all prospects - check for prospect names instead of table rows
    expect(screen.getByText('Prospect 1')).toBeInTheDocument();
    expect(screen.getByText('Prospect 25')).toBeInTheDocument();
  });
});
