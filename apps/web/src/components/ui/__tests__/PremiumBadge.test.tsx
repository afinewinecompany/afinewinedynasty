import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { PremiumBadge } from '../PremiumBadge';

describe('PremiumBadge Component', () => {
  describe('Rendering', () => {
    it('renders with default props', () => {
      render(<PremiumBadge />);

      expect(screen.getByText('Premium')).toBeInTheDocument();
      const badge = screen.getByText('Premium').parentElement;
      expect(badge).toHaveClass('px-3', 'py-1', 'text-sm'); // md size classes
    });

    it('renders without text when showText is false', () => {
      render(<PremiumBadge showText={false} />);

      expect(screen.queryByText('Premium')).not.toBeInTheDocument();
    });

    it('renders with small size', () => {
      render(<PremiumBadge size="sm" />);

      const badge = screen.getByText('Premium').parentElement;
      expect(badge).toHaveClass('px-2', 'py-0.5', 'text-xs');
    });

    it('renders with large size', () => {
      render(<PremiumBadge size="lg" />);

      const badge = screen.getByText('Premium').parentElement;
      expect(badge).toHaveClass('px-4', 'py-1.5', 'text-base');
    });

    it('applies custom className', () => {
      render(<PremiumBadge className="custom-class" />);

      const badge = screen.getByText('Premium').parentElement;
      expect(badge).toHaveClass('custom-class');
    });
  });

  describe('Styling', () => {
    it('has gradient background', () => {
      render(<PremiumBadge />);

      const badge = screen.getByText('Premium').parentElement;
      expect(badge).toHaveClass('bg-gradient-to-r', 'from-amber-500', 'to-amber-600');
    });

    it('has hover effects', () => {
      render(<PremiumBadge />);

      const badge = screen.getByText('Premium').parentElement;
      expect(badge).toHaveClass('hover:from-amber-600', 'hover:to-amber-700');
    });

    it('includes star icon', () => {
      const { container } = render(<PremiumBadge />);

      const svg = container.querySelector('svg');
      expect(svg).toBeInTheDocument();
      expect(svg).toHaveClass('fill-current');
    });
  });
});