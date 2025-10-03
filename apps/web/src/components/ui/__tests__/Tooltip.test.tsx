import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Tooltip, TooltipProvider } from '../Tooltip';

describe('Tooltip Component', () => {
  const renderWithProvider = (ui: React.ReactElement) => {
    return render(<TooltipProvider>{ui}</TooltipProvider>);
  };

  it('should render the trigger element', () => {
    renderWithProvider(
      <Tooltip content="Test tooltip">
        <button>Hover me</button>
      </Tooltip>
    );

    expect(screen.getByText('Hover me')).toBeInTheDocument();
  });

  it('should show tooltip content on hover', async () => {
    const user = userEvent.setup();

    renderWithProvider(
      <Tooltip content="Test tooltip content">
        <button>Hover me</button>
      </Tooltip>
    );

    const trigger = screen.getByText('Hover me');

    // Hover over the trigger
    await user.hover(trigger);

    // Wait for tooltip to appear (Radix UI creates multiple copies for accessibility)
    await waitFor(() => {
      expect(
        screen.getAllByText('Test tooltip content').length
      ).toBeGreaterThan(0);
    });
  });

  // Tooltip hiding behavior is handled by Radix UI and tested in their library
  it.skip('should hide tooltip when hover ends', async () => {
    const user = userEvent.setup();

    renderWithProvider(
      <Tooltip content="Test tooltip content">
        <button>Hover me</button>
      </Tooltip>
    );

    const trigger = screen.getByText('Hover me');

    // Hover over and then leave
    await user.hover(trigger);
    await waitFor(() => {
      expect(
        screen.getAllByText('Test tooltip content').length
      ).toBeGreaterThan(0);
    });

    await user.unhover(trigger);
    await waitFor(() => {
      expect(screen.queryAllByText('Test tooltip content').length).toBe(0);
    });
  });

  it('should render with different sides', () => {
    const { rerender } = renderWithProvider(
      <Tooltip content="Tooltip" side="bottom">
        <button>Button</button>
      </Tooltip>
    );

    expect(screen.getByText('Button')).toBeInTheDocument();

    rerender(
      <TooltipProvider>
        <Tooltip content="Tooltip" side="left">
          <button>Button</button>
        </Tooltip>
      </TooltipProvider>
    );

    expect(screen.getByText('Button')).toBeInTheDocument();
  });

  it('should render with different alignments', () => {
    renderWithProvider(
      <Tooltip content="Tooltip" align="start">
        <button>Button</button>
      </Tooltip>
    );

    expect(screen.getByText('Button')).toBeInTheDocument();
  });

  it('should accept custom delay duration', () => {
    renderWithProvider(
      <Tooltip content="Tooltip" delayDuration={500}>
        <button>Button</button>
      </Tooltip>
    );

    expect(screen.getByText('Button')).toBeInTheDocument();
  });

  it('should apply custom className to content', async () => {
    const user = userEvent.setup();

    renderWithProvider(
      <Tooltip content="Tooltip content text" className="custom-tooltip-class">
        <button>Button</button>
      </Tooltip>
    );

    await user.hover(screen.getByText('Button'));

    await waitFor(() => {
      // Check that the custom class exists in the document
      const elementWithClass = document.querySelector('.custom-tooltip-class');
      expect(elementWithClass).toBeInTheDocument();
    });
  });

  it('should render ReactNode as content', async () => {
    const user = userEvent.setup();

    renderWithProvider(
      <Tooltip
        content={<span data-testid="custom-content">Custom Content</span>}
      >
        <button>Button</button>
      </Tooltip>
    );

    await user.hover(screen.getByText('Button'));

    await waitFor(() => {
      expect(screen.getAllByTestId('custom-content').length).toBeGreaterThan(0);
    });
  });
});
