import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { jest } from '@jest/globals';
import ProspectOutlook from '../ProspectOutlook';

// Mock the custom hook
jest.mock('@/hooks/useProspectOutlook', () => ({
  useProspectOutlook: jest.fn(),
}));

const mockUseProspectOutlook = require('@/hooks/useProspectOutlook').useProspectOutlook as jest.MockedFunction<any>;

// Mock fetch
global.fetch = jest.fn();

const mockOutlookData = {
  narrative: "John Smith is a 21-year-old shortstop in the Yankees system currently at Double-A. His exceptional hitting ability stands out as his premier tool and drives much of his upside. Supporting this is solid plate discipline, adding depth to his offensive profile. The model projects 75.0% success probability with medium risk, expecting arrival within 2 years with 85.0% confidence.",
  quality_metrics: {
    quality_score: 85.0,
    readability_score: 78.0,
    coherence_score: 82.0,
    sentence_count: 4,
    word_count: 63,
    grammar_issues: [],
    content_issues: []
  },
  generated_at: "2024-01-15T10:30:00Z",
  template_version: "v1.0",
  model_version: "v1.0",
  risk_level: "Medium",
  timeline: "within 2 years",
  prospect_id: "123"
};

describe('ProspectOutlook', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders loading state', () => {
    mockUseProspectOutlook.mockReturnValue({
      data: null,
      loading: true,
      error: null,
      refetch: jest.fn(),
    });

    render(<ProspectOutlook prospectId="123" />);

    expect(screen.getByText('AI Outlook')).toBeInTheDocument();
    expect(screen.getByRole('status')).toBeInTheDocument(); // LoadingSpinner
  });

  it('renders error state with retry button', () => {
    const mockRefetch = jest.fn();
    mockUseProspectOutlook.mockReturnValue({
      data: null,
      loading: false,
      error: 'Failed to fetch outlook',
      refetch: mockRefetch,
    });

    render(<ProspectOutlook prospectId="123" />);

    expect(screen.getByText('AI Outlook')).toBeInTheDocument();
    expect(screen.getByText('Failed to generate prospect outlook')).toBeInTheDocument();

    const retryButton = screen.getByRole('button', { name: /retry/i });
    fireEvent.click(retryButton);

    expect(mockRefetch).toHaveBeenCalledTimes(1);
  });

  it('renders outlook data successfully', () => {
    mockUseProspectOutlook.mockReturnValue({
      data: mockOutlookData,
      loading: false,
      error: null,
      refetch: jest.fn(),
    });

    render(<ProspectOutlook prospectId="123" />);

    expect(screen.getByText('AI Outlook')).toBeInTheDocument();
    expect(screen.getByText(/John Smith is a 21-year-old shortstop/)).toBeInTheDocument();
    expect(screen.getByText('Medium Risk')).toBeInTheDocument();
    expect(screen.getByText('within 2 years')).toBeInTheDocument();
  });

  it('renders compact version', () => {
    mockUseProspectOutlook.mockReturnValue({
      data: mockOutlookData,
      loading: false,
      error: null,
      refetch: jest.fn(),
    });

    render(<ProspectOutlook prospectId="123" compact />);

    expect(screen.getByText('AI Outlook')).toBeInTheDocument();
    expect(screen.getByText(/John Smith is a 21-year-old shortstop/)).toBeInTheDocument();

    // Should not show quality metrics toggle in compact mode
    expect(screen.queryByText(/Quality Score:/)).not.toBeInTheDocument();

    // Should not show controls in compact mode
    expect(screen.queryByText('Refresh')).not.toBeInTheDocument();
    expect(screen.queryByText('Helpful?')).not.toBeInTheDocument();
  });

  it('shows quality metrics when expanded', () => {
    mockUseProspectOutlook.mockReturnValue({
      data: mockOutlookData,
      loading: false,
      error: null,
      refetch: jest.fn(),
    });

    render(<ProspectOutlook prospectId="123" />);

    // Click to expand quality metrics
    const qualityToggle = screen.getByText(/Quality Score: 85/);
    fireEvent.click(qualityToggle);

    expect(screen.getByText('Quality Metrics')).toBeInTheDocument();
    expect(screen.getByText('Overall')).toBeInTheDocument();
    expect(screen.getByText('Clarity')).toBeInTheDocument();
    expect(screen.getByText('Flow')).toBeInTheDocument();
    expect(screen.getByText('4 sentences • 63 words')).toBeInTheDocument();
  });

  it('handles refresh action', async () => {
    const mockRefetch = jest.fn();
    mockUseProspectOutlook.mockReturnValue({
      data: mockOutlookData,
      loading: false,
      error: null,
      refetch: mockRefetch,
    });

    render(<ProspectOutlook prospectId="123" />);

    const refreshButton = screen.getByText('Refresh');
    fireEvent.click(refreshButton);

    expect(mockRefetch).toHaveBeenCalledTimes(1);
  });

  it('handles feedback submission', async () => {
    const mockFetch = fetch as jest.MockedFunction<typeof fetch>;
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: jest.fn().mockResolvedValue({}),
    } as any);

    mockUseProspectOutlook.mockReturnValue({
      data: mockOutlookData,
      loading: false,
      error: null,
      refetch: jest.fn(),
    });

    render(<ProspectOutlook prospectId="123" />);

    // Click thumbs up
    const thumbsUpButton = screen.getByTitle('Mark as helpful');
    fireEvent.click(thumbsUpButton);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/ml/outlook/123/feedback',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: expect.stringContaining('"helpful":true'),
        })
      );
    });
  });

  it('handles no data state', () => {
    mockUseProspectOutlook.mockReturnValue({
      data: null,
      loading: false,
      error: null,
      refetch: jest.fn(),
    });

    render(<ProspectOutlook prospectId="123" />);

    expect(screen.getByText('AI Outlook')).toBeInTheDocument();
    expect(screen.getByText('No outlook available for this prospect')).toBeInTheDocument();
  });

  it('displays metadata correctly', () => {
    mockUseProspectOutlook.mockReturnValue({
      data: mockOutlookData,
      loading: false,
      error: null,
      refetch: jest.fn(),
    });

    render(<ProspectOutlook prospectId="123" />);

    expect(screen.getByText(/Generated 1\/15\/2024/)).toBeInTheDocument();
    expect(screen.getByText(/Model v1.0/)).toBeInTheDocument();
    expect(screen.getByText(/Template v1.0/)).toBeInTheDocument();
  });

  it('handles fetch error gracefully in feedback', async () => {
    const mockFetch = fetch as jest.MockedFunction<typeof fetch>;
    mockFetch.mockRejectedValueOnce(new Error('Network error'));

    // Mock console.error to avoid noise in tests
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

    mockUseProspectOutlook.mockReturnValue({
      data: mockOutlookData,
      loading: false,
      error: null,
      refetch: jest.fn(),
    });

    render(<ProspectOutlook prospectId="123" />);

    const thumbsUpButton = screen.getByTitle('Mark as helpful');
    fireEvent.click(thumbsUpButton);

    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith('Failed to submit feedback:', expect.any(Error));
    });

    consoleSpy.mockRestore();
  });

  it('applies correct styling for different risk levels', () => {
    const lowRiskData = { ...mockOutlookData, risk_level: 'Low' };
    const highRiskData = { ...mockOutlookData, risk_level: 'High' };

    // Test Low risk
    mockUseProspectOutlook.mockReturnValue({
      data: lowRiskData,
      loading: false,
      error: null,
      refetch: jest.fn(),
    });

    const { rerender } = render(<ProspectOutlook prospectId="123" />);
    expect(screen.getByText('Low Risk')).toHaveClass('bg-green-100', 'text-green-800');

    // Test High risk
    mockUseProspectOutlook.mockReturnValue({
      data: highRiskData,
      loading: false,
      error: null,
      refetch: jest.fn(),
    });

    rerender(<ProspectOutlook prospectId="123" />);
    expect(screen.getByText('High Risk')).toHaveClass('bg-red-100', 'text-red-800');
  });
});