/**
 * Test suite for PlanCard component.
 *
 * @module components/subscription/__tests__/PlanCard.test
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { PlanCard } from '../PlanCard';
import { SUBSCRIPTION_PLANS } from '@/types/subscription';

describe('PlanCard Component', () => {
  const mockFreePlan = SUBSCRIPTION_PLANS[0];
  const mockPremiumPlan = SUBSCRIPTION_PLANS[1];
  const mockOnSelect = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Rendering', () => {
    it('should render plan card with correct details', () => {
      render(<PlanCard plan={mockPremiumPlan} onSelect={mockOnSelect} />);

      expect(screen.getByText('Premium')).toBeInTheDocument();
      expect(screen.getByText('$9.99')).toBeInTheDocument();
      expect(screen.getByText('/month')).toBeInTheDocument();
      expect(screen.getByText('Subscribe Now')).toBeInTheDocument();
    });

    it('should display all features', () => {
      render(<PlanCard plan={mockPremiumPlan} onSelect={mockOnSelect} />);

      mockPremiumPlan.features.forEach((feature) => {
        expect(screen.getByText(feature)).toBeInTheDocument();
      });
    });

    it('should display limitations for free plan', () => {
      render(<PlanCard plan={mockFreePlan} onSelect={mockOnSelect} />);

      mockFreePlan.limitations?.forEach((limitation) => {
        expect(screen.getByText(limitation)).toBeInTheDocument();
      });
    });

    it('should show "Most Popular" badge for highlighted plans', () => {
      render(<PlanCard plan={mockPremiumPlan} onSelect={mockOnSelect} />);

      expect(screen.getByText('Most Popular')).toBeInTheDocument();
    });

    it('should show "Current Plan" badge when currentPlan is true', () => {
      render(
        <PlanCard
          plan={mockPremiumPlan}
          currentPlan={true}
          onSelect={mockOnSelect}
        />
      );

      expect(screen.getByText('Current Plan')).toBeInTheDocument();
      expect(screen.getByText('Your Current Plan')).toBeInTheDocument();
    });
  });

  describe('Interactions', () => {
    it('should call onSelect when button is clicked', () => {
      render(<PlanCard plan={mockPremiumPlan} onSelect={mockOnSelect} />);

      const button = screen.getByRole('button', { name: /Subscribe Now/i });
      fireEvent.click(button);

      expect(mockOnSelect).toHaveBeenCalledTimes(1);
    });

    it('should disable button when isLoading is true', () => {
      render(
        <PlanCard
          plan={mockPremiumPlan}
          onSelect={mockOnSelect}
          isLoading={true}
        />
      );

      const button = screen.getByRole('button', { name: /Processing/i });
      expect(button).toBeDisabled();
    });

    it('should not show action button when currentPlan is true', () => {
      render(
        <PlanCard
          plan={mockPremiumPlan}
          currentPlan={true}
          onSelect={mockOnSelect}
        />
      );

      expect(screen.queryByText('Subscribe Now')).not.toBeInTheDocument();
      expect(screen.getByText('Your Current Plan')).toBeDisabled();
    });

    it('should show "Get Started" for free plan', () => {
      render(<PlanCard plan={mockFreePlan} onSelect={mockOnSelect} />);

      expect(screen.getByText('Get Started')).toBeInTheDocument();
    });
  });

  describe('Styling', () => {
    it('should apply special styling for highlighted plans', () => {
      const { container } = render(
        <PlanCard plan={mockPremiumPlan} onSelect={mockOnSelect} />
      );

      const card = container.querySelector('.border-primary');
      expect(card).toBeInTheDocument();
      expect(card).toHaveClass('shadow-lg');
    });

    it('should show green check icons for features', () => {
      render(<PlanCard plan={mockPremiumPlan} onSelect={mockOnSelect} />);

      const checkIcons = screen.getAllByTestId('check-icon');
      checkIcons.forEach((icon) => {
        expect(icon).toHaveClass('text-green-600');
      });
    });

    it('should show red X icons for limitations', () => {
      render(<PlanCard plan={mockFreePlan} onSelect={mockOnSelect} />);

      const xIcons = screen.getAllByTestId('x-icon');
      xIcons.forEach((icon) => {
        expect(icon).toHaveClass('text-red-600');
      });
    });
  });
});
