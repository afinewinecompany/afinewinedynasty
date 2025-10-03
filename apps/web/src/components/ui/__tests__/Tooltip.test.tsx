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

    // Wait for tooltip to appear
    await waitFor(() => {
      expect(screen.getByText('Test tooltip content')).toBeInTheDocument();
    });
  });

  it('should hide tooltip when hover ends', async () => {
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
      expect(screen.getByText('Test tooltip content')).toBeInTheDocument();
    });

    await user.unhover(trigger);
    await waitFor(() => {
      expect(screen.queryByText('Test tooltip content')).not.toBeInTheDocument();
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
      <Tooltip content="Tooltip" className="custom-class">
        <button>Button</button>
      </Tooltip>
    );

    await user.hover(screen.getByText('Button'));

    await waitFor(() => {
      const tooltipContent = screen.getByText('Tooltip');
      expect(tooltipContent.parentElement).toHaveClass('custom-class');
    });
  });

  it('should render ReactNode as content', async () => {
    const user = userEvent.setup();

    renderWithProvider(
      <Tooltip content={<span data-testid="custom-content">Custom Content</span>}>
        <button>Button</button>
      </Tooltip>
    );

    await user.hover(screen.getByText('Button'));

    await waitFor(() => {
      expect(screen.getByTestId('custom-content')).toBeInTheDocument();
      expect(screen.getByText('Custom Content')).toBeInTheDocument();
    });
  });
});