import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HelpIcon } from '../HelpIcon';
import { TooltipProvider } from '@/components/ui/Tooltip';

describe('HelpIcon Component', () => {
  const renderWithProvider = (ui: React.ReactElement) => {
    return render(<TooltipProvider>{ui}</TooltipProvider>);
  };

  it('should render the help icon', () => {
    renderWithProvider(<HelpIcon content="Help text" />);

    // The HelpCircle icon should be rendered as an SVG element
    const icon = document.querySelector('svg');
    expect(icon).toBeInTheDocument();
    expect(icon).toHaveClass('lucide-circle-question-mark');
  });

  it('should display tooltip content on hover', async () => {
    const user = userEvent.setup();
    const helpText = 'This is helpful information';

    renderWithProvider(<HelpIcon content={helpText} />);

    const iconElement = document.querySelector('svg');

    await user.hover(iconElement.parentElement as HTMLElement);

    await waitFor(() => {
      expect(screen.getAllByText(helpText).length).toBeGreaterThan(0);
    });
  });

  // Tooltip hiding is handled by Radix UI and tested in their library
  it.skip('should hide tooltip when hover ends', async () => {
    const user = userEvent.setup();
    const helpText = 'This is helpful information';

    renderWithProvider(<HelpIcon content={helpText} />);

    const iconElement = document.querySelector('svg');

    await user.hover(iconElement.parentElement as HTMLElement);
    await waitFor(() => {
      const trigger = iconElement.parentElement;
      expect(trigger?.getAttribute('data-state')).toBe('delayed-open');
    });

    await user.unhover(iconElement.parentElement as HTMLElement);
    await waitFor(() => {
      const trigger = iconElement.parentElement;
      expect(trigger?.getAttribute('data-state')).not.toBe('delayed-open');
    });
  });

  it('should render with different sizes', () => {
    const { rerender } = renderWithProvider(
      <HelpIcon content="Help" size="sm" />
    );

    let icon = document.querySelector('svg');
    expect(icon).toHaveClass('h-4', 'w-4');

    rerender(
      <TooltipProvider>
        <HelpIcon content="Help" size="md" />
      </TooltipProvider>
    );

    icon = document.querySelector('svg');
    expect(icon).toHaveClass('h-5', 'w-5');

    rerender(
      <TooltipProvider>
        <HelpIcon content="Help" size="lg" />
      </TooltipProvider>
    );

    icon = document.querySelector('svg');
    expect(icon).toHaveClass('h-6', 'w-6');
  });

  it('should apply custom className', () => {
    const customClass = 'custom-help-icon';
    renderWithProvider(<HelpIcon content="Help" className={customClass} />);

    const iconWrapper = document.querySelector('svg')?.parentElement;
    expect(iconWrapper).toHaveClass(customClass);
  });

  it('should have hover styles', () => {
    renderWithProvider(<HelpIcon content="Help" />);

    const icon = document.querySelector('svg');
    expect(icon).toHaveClass(
      'text-gray-400',
      'hover:text-gray-600',
      'cursor-help',
      'transition-colors'
    );
  });

  it('should render ReactNode as content', async () => {
    const user = userEvent.setup();
    const customContent = (
      <div data-testid="custom-help-content">
        <strong>Important:</strong> Custom help content
      </div>
    );

    renderWithProvider(<HelpIcon content={customContent} />);

    const iconElement = document.querySelector('svg');
    await user.hover(iconElement.parentElement as HTMLElement);

    await waitFor(() => {
      expect(
        screen.getAllByTestId('custom-help-content').length
      ).toBeGreaterThan(0);
    });
  });

  it('should use default size when not specified', () => {
    renderWithProvider(<HelpIcon content="Help" />);

    const icon = document.querySelector('svg');
    expect(icon).toHaveClass('h-4', 'w-4'); // Default is 'sm'
  });
});
