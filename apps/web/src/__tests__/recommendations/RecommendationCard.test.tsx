/**
 * @jest-environment jsdom
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { RecommendationCard } from '@/components/recommendations/RecommendationCard';
import type { RecommendationDetails } from '@/types/recommendations';

describe('RecommendationCard Component', () => {
  const mockRecommendation: RecommendationDetails = {
    prospect_id: 1,
    fit_score: 85,
    position_fit: 90,
    timeline_fit: 80,
    value_rating: 'high',
    explanation: 'This prospect is a great fit for your team needs',
    confidence: 'high',
  };

  const defaultProps = {
    recommendation: mockRecommendation,
    prospectName: 'Jackson Holliday',
    position: 'SS',
    organization: 'BAL',
    etaYear: 2024,
    rank: 1,
  };

  it('should render prospect information correctly', () => {
    render(<RecommendationCard {...defaultProps} />);

    expect(screen.getByText('Jackson Holliday')).toBeInTheDocument();
    expect(screen.getByText('SS')).toBeInTheDocument();
    expect(screen.getByText('BAL')).toBeInTheDocument();
    expect(screen.getByText('ETA: 2024')).toBeInTheDocument();
    expect(screen.getByText('#1')).toBeInTheDocument();
  });

  it('should display fit score correctly', () => {
    render(<RecommendationCard {...defaultProps} />);

    expect(screen.getByText('85')).toBeInTheDocument();
    expect(screen.getByText('Fit Score')).toBeInTheDocument();
  });

  it('should display breakdown metrics', () => {
    render(<RecommendationCard {...defaultProps} />);

    expect(screen.getByText('Position Fit')).toBeInTheDocument();
    expect(screen.getByText('90%')).toBeInTheDocument();

    expect(screen.getByText('Timeline Fit')).toBeInTheDocument();
    expect(screen.getByText('80%')).toBeInTheDocument();
  });

  it('should display value rating and confidence', () => {
    render(<RecommendationCard {...defaultProps} />);

    expect(screen.getByText('High Value')).toBeInTheDocument();
    expect(screen.getByText('high confidence')).toBeInTheDocument();
  });

  it('should display explanation', () => {
    render(<RecommendationCard {...defaultProps} />);

    expect(
      screen.getByText('This prospect is a great fit for your team needs')
    ).toBeInTheDocument();
  });

  it('should expand and collapse details', () => {
    render(<RecommendationCard {...defaultProps} />);

    // Initially collapsed
    expect(screen.queryByText('Overall Fit')).not.toBeInTheDocument();

    // Expand
    const expandButton = screen.getByText('Show detailed metrics');
    fireEvent.click(expandButton);

    // Check expanded content
    expect(screen.getByText('Overall Fit')).toBeInTheDocument();
    expect(screen.getByText('Position Match')).toBeInTheDocument();
    expect(screen.getByText('Timeline Match')).toBeInTheDocument();

    // Collapse
    const collapseButton = screen.getByText('Show less');
    fireEvent.click(collapseButton);

    expect(screen.queryByText('Overall Fit')).not.toBeInTheDocument();
  });

  it('should call onClick when card is clicked', () => {
    const mockOnClick = jest.fn();
    render(<RecommendationCard {...defaultProps} onClick={mockOnClick} />);

    const card = screen.getByText('Jackson Holliday').closest('.cursor-pointer');
    if (card) {
      fireEvent.click(card);
    }

    expect(mockOnClick).toHaveBeenCalledWith(1);
  });

  it('should not call onClick when expand button is clicked', () => {
    const mockOnClick = jest.fn();
    render(<RecommendationCard {...defaultProps} onClick={mockOnClick} />);

    const expandButton = screen.getByText('Show detailed metrics');
    fireEvent.click(expandButton);

    // onClick should not be called when expanding details
    expect(mockOnClick).not.toHaveBeenCalled();
  });

  it('should render without optional props', () => {
    const minimalProps = {
      recommendation: mockRecommendation,
      prospectName: 'Test Prospect',
      position: 'OF',
    };

    render(<RecommendationCard {...minimalProps} />);

    expect(screen.getByText('Test Prospect')).toBeInTheDocument();
    expect(screen.queryByText('#')).not.toBeInTheDocument();
    expect(screen.queryByText(/ETA:/)).not.toBeInTheDocument();
  });

  it('should render high fit score', () => {
    render(<RecommendationCard {...defaultProps} />);

    // Check that fit score is displayed
    expect(screen.getByText('85')).toBeInTheDocument();
    expect(screen.getByText('Fit Score')).toBeInTheDocument();
  });

  it('should render medium fit score', () => {
    const mediumFitProps = {
      ...defaultProps,
      recommendation: {
        ...mockRecommendation,
        fit_score: 65,
      },
    };

    render(<RecommendationCard {...mediumFitProps} />);

    // Check that fit score is displayed
    expect(screen.getByText('65')).toBeInTheDocument();
    expect(screen.getByText('Fit Score')).toBeInTheDocument();
  });

  it('should display elite value rating correctly', () => {
    const eliteProps = {
      ...defaultProps,
      recommendation: {
        ...mockRecommendation,
        value_rating: 'elite' as const,
      },
    };

    render(<RecommendationCard {...eliteProps} />);

    expect(screen.getByText('Elite Value')).toBeInTheDocument();
  });

  it('should display speculative value rating correctly', () => {
    const speculativeProps = {
      ...defaultProps,
      recommendation: {
        ...mockRecommendation,
        value_rating: 'speculative' as const,
      },
    };

    render(<RecommendationCard {...speculativeProps} />);

    expect(screen.getByText('Speculative Value')).toBeInTheDocument();
  });

  it('should display medium confidence badge', () => {
    const mediumConfidenceProps = {
      ...defaultProps,
      recommendation: {
        ...mockRecommendation,
        confidence: 'medium' as const,
      },
    };

    render(<RecommendationCard {...mediumConfidenceProps} />);

    expect(screen.getByText('medium confidence')).toBeInTheDocument();
  });

  it('should display low confidence badge', () => {
    const lowConfidenceProps = {
      ...defaultProps,
      recommendation: {
        ...mockRecommendation,
        confidence: 'low' as const,
      },
    };

    render(<RecommendationCard {...lowConfidenceProps} />);

    expect(screen.getByText('low confidence')).toBeInTheDocument();
  });
});
