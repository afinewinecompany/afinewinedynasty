/**
 * @jest-environment jsdom
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { MobileProspectCard } from '@/components/ui/MobileProspectCard';
import type { ProspectRanking } from '@/types/prospect';

describe('MobileProspectCard Component', () => {
  const mockProspect: ProspectRanking = {
    id: '123',
    rank: 5,
    name: 'John Doe',
    position: 'SS',
    organization: 'Yankees',
    eta: '2025',
    mlPrediction: {
      confidence: 0.85,
      projectedWAR: 3.5,
    },
    stats: {
      battingAverage: '.285',
      ops: '.850',
      homeRuns: '15',
    },
    scoutingGrades: {
      hit: 60,
      power: 55,
      speed: 50,
      fielding: 65,
      arm: 60,
    },
    aiOutlook: 'Strong defensive shortstop with developing power potential.',
  };

  const mockOnQuickAction = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Priority 1 Information Display', () => {
    it('should always display rank, name, position, and organization', () => {
      render(
        <MobileProspectCard
          prospect={mockProspect}
          onQuickAction={mockOnQuickAction}
        />
      );

      expect(screen.getByText('#5')).toBeInTheDocument();
      expect(screen.getByText('John Doe')).toBeInTheDocument();
      expect(screen.getByText('SS')).toBeInTheDocument();
      expect(screen.getByText('Yankees')).toBeInTheDocument();
    });

    it('should display ML prediction confidence', () => {
      render(
        <MobileProspectCard
          prospect={mockProspect}
          onQuickAction={mockOnQuickAction}
        />
      );

      expect(screen.getByText('85% confidence')).toBeInTheDocument();
    });

    it('should display ETA badge', () => {
      render(
        <MobileProspectCard
          prospect={mockProspect}
          onQuickAction={mockOnQuickAction}
        />
      );

      expect(screen.getByText('ETA 2025')).toBeInTheDocument();
    });
  });

  describe('Quick Actions', () => {
    it('should trigger watchlist action when button clicked', () => {
      render(
        <MobileProspectCard
          prospect={mockProspect}
          onQuickAction={mockOnQuickAction}
          isInWatchlist={false}
        />
      );

      const watchlistButton = screen.getByLabelText('Add to watchlist');
      fireEvent.click(watchlistButton);

      expect(mockOnQuickAction).toHaveBeenCalledWith('watchlist', '123');
    });

    it('should show filled star when in watchlist', () => {
      render(
        <MobileProspectCard
          prospect={mockProspect}
          onQuickAction={mockOnQuickAction}
          isInWatchlist={true}
        />
      );

      const watchlistButton = screen.getByLabelText('Remove from watchlist');
      expect(watchlistButton).toHaveTextContent('★');
    });

    it('should trigger compare action when button clicked', () => {
      render(
        <MobileProspectCard
          prospect={mockProspect}
          onQuickAction={mockOnQuickAction}
        />
      );

      const compareButton = screen.getByLabelText('Add to comparison');
      fireEvent.click(compareButton);

      expect(mockOnQuickAction).toHaveBeenCalledWith('compare', '123');
    });

    it('should have minimum touch target size of 44px', () => {
      const { container } = render(
        <MobileProspectCard
          prospect={mockProspect}
          onQuickAction={mockOnQuickAction}
        />
      );

      const buttons = container.querySelectorAll('button');
      buttons.forEach((button) => {
        const styles = window.getComputedStyle(button);
        expect(button.className).toContain('h-[44px]');
      });
    });
  });

  describe('Progressive Disclosure', () => {
    it('should show expand button initially', () => {
      render(
        <MobileProspectCard
          prospect={mockProspect}
          onQuickAction={mockOnQuickAction}
        />
      );

      expect(screen.getByText('View stats & details ▼')).toBeInTheDocument();
    });

    it('should expand to show Priority 2 information when clicked', () => {
      render(
        <MobileProspectCard
          prospect={mockProspect}
          onQuickAction={mockOnQuickAction}
        />
      );

      const expandButton = screen.getByText('View stats & details ▼');
      fireEvent.click(expandButton);

      // Check for expanded content
      expect(screen.getByText('Current Season')).toBeInTheDocument();
      expect(screen.getByText('AVG:')).toBeInTheDocument();
      expect(screen.getByText('.285')).toBeInTheDocument();
      expect(screen.getByText('Scouting Grades')).toBeInTheDocument();
      expect(screen.getByText('AI Outlook')).toBeInTheDocument();
    });

    it('should collapse when "Show less" is clicked', () => {
      render(
        <MobileProspectCard
          prospect={mockProspect}
          onQuickAction={mockOnQuickAction}
        />
      );

      // Expand
      const expandButton = screen.getByText('View stats & details ▼');
      fireEvent.click(expandButton);

      // Collapse
      const collapseButton = screen.getByText('Show less ▲');
      fireEvent.click(collapseButton);

      // Check that expanded content is hidden
      expect(screen.queryByText('Current Season')).not.toBeInTheDocument();
      expect(screen.getByText('View stats & details ▼')).toBeInTheDocument();
    });
  });

  describe('Confidence Color Coding', () => {
    it('should show green color for high confidence (>=80%)', () => {
      render(
        <MobileProspectCard
          prospect={mockProspect}
          onQuickAction={mockOnQuickAction}
        />
      );

      const confidenceText = screen.getByText('85% confidence');
      expect(confidenceText.className).toContain('text-green-600');
    });

    it('should show yellow color for medium confidence (60-79%)', () => {
      const mediumConfidenceProspect = {
        ...mockProspect,
        mlPrediction: { confidence: 0.65, projectedWAR: 2.5 },
      };

      render(
        <MobileProspectCard
          prospect={mediumConfidenceProspect}
          onQuickAction={mockOnQuickAction}
        />
      );

      const confidenceText = screen.getByText('65% confidence');
      expect(confidenceText.className).toContain('text-yellow-600');
    });

    it('should show red color for low confidence (<60%)', () => {
      const lowConfidenceProspect = {
        ...mockProspect,
        mlPrediction: { confidence: 0.45, projectedWAR: 1.5 },
      };

      render(
        <MobileProspectCard
          prospect={lowConfidenceProspect}
          onQuickAction={mockOnQuickAction}
        />
      );

      const confidenceText = screen.getByText('45% confidence');
      expect(confidenceText.className).toContain('text-red-600');
    });
  });

  describe('Missing Data Handling', () => {
    it('should handle missing stats gracefully', () => {
      const prospectWithoutStats = {
        ...mockProspect,
        stats: undefined,
      };

      render(
        <MobileProspectCard
          prospect={prospectWithoutStats}
          onQuickAction={mockOnQuickAction}
        />
      );

      // Expand to see stats section
      const expandButton = screen.getByText('View stats & details ▼');
      fireEvent.click(expandButton);

      expect(screen.getByText('AVG:')).toBeInTheDocument();
      expect(screen.getByText('--')).toBeInTheDocument();
    });

    it('should handle missing scouting grades', () => {
      const prospectWithoutGrades = {
        ...mockProspect,
        scoutingGrades: undefined,
      };

      render(
        <MobileProspectCard
          prospect={prospectWithoutGrades}
          onQuickAction={mockOnQuickAction}
        />
      );

      // Expand to see details
      const expandButton = screen.getByText('View stats & details ▼');
      fireEvent.click(expandButton);

      // Scouting Grades section should not be rendered
      expect(screen.queryByText('Scouting Grades')).not.toBeInTheDocument();
    });
  });
});
