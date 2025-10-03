/**
 * @jest-environment jsdom
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { RiskToleranceSettings } from '@/components/recommendations/RiskToleranceSettings';
import { useRecommendations } from '@/hooks/useRecommendations';
import type { UserPreferences } from '@/types/recommendations';

// Mock the hook
jest.mock('@/hooks/useRecommendations');

const mockUseRecommendations = useRecommendations as jest.MockedFunction<
  typeof useRecommendations
>;

describe('RiskToleranceSettings Component', () => {
  const mockPreferences: UserPreferences = {
    risk_tolerance: 'balanced',
    prefer_win_now: true,
    prefer_rebuild: false,
    position_priorities: ['SP', 'OF'],
    prefer_buy_low: true,
    prefer_sell_high: false,
  };

  const defaultMockReturn = {
    teamNeeds: null,
    prospectRecommendations: [],
    tradeTargets: null,
    draftStrategy: null,
    stashCandidates: null,
    preferences: null,
    loading: {
      teamNeeds: false,
      prospects: false,
      tradeTargets: false,
      draftStrategy: false,
      stashCandidates: false,
      preferences: false,
    },
    error: {
      teamNeeds: null,
      prospects: null,
      tradeTargets: null,
      draftStrategy: null,
      stashCandidates: null,
      preferences: null,
    },
    fetchTeamNeeds: jest.fn(),
    fetchProspectRecommendations: jest.fn(),
    fetchTradeTargets: jest.fn(),
    fetchDraftStrategy: jest.fn(),
    fetchStashCandidates: jest.fn(),
    fetchPreferences: jest.fn(),
    updatePreferences: jest.fn(),
    clearAll: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockUseRecommendations.mockReturnValue(defaultMockReturn);
  });

  it('should render loading state', () => {
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      loading: { ...defaultMockReturn.loading, preferences: true },
    });

    render(<RiskToleranceSettings />);

    expect(screen.getByText('Loading preferences...')).toBeInTheDocument();
  });

  it('should display preferences correctly', () => {
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      preferences: mockPreferences,
    });

    render(<RiskToleranceSettings />);

    // Check title
    expect(screen.getByText('Recommendation Preferences')).toBeInTheDocument();
    expect(
      screen.getByText('Customize how prospects are recommended to you')
    ).toBeInTheDocument();

    // Check risk tolerance description
    expect(screen.getByText('Balanced')).toBeInTheDocument();
    expect(
      screen.getByText('Mix of safe and high-upside prospects')
    ).toBeInTheDocument();
  });

  it('should call fetchPreferences on mount when autoLoad is true', () => {
    const mockFetch = jest.fn();
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      fetchPreferences: mockFetch,
    });

    render(<RiskToleranceSettings autoLoad={true} />);

    expect(mockFetch).toHaveBeenCalled();
  });

  it('should not call fetchPreferences on mount when autoLoad is false', () => {
    const mockFetch = jest.fn();
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      fetchPreferences: mockFetch,
    });

    render(<RiskToleranceSettings autoLoad={false} />);

    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('should update form when preferences load', () => {
    const { rerender } = render(<RiskToleranceSettings />);

    // Initially no preferences
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      preferences: mockPreferences,
    });

    rerender(<RiskToleranceSettings />);

    // Preferences should be loaded
    expect(screen.getByText('Balanced')).toBeInTheDocument();
  });

  it('should enable Save button when changes are made', () => {
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      preferences: mockPreferences,
    });

    render(<RiskToleranceSettings />);

    // Initially disabled
    const saveButton = screen.getByText('Save Preferences');
    expect(saveButton).toBeDisabled();

    // Make a change - toggle a position
    const positionBadge = screen.getByText('C');
    fireEvent.click(positionBadge);

    // Now enabled
    expect(saveButton).not.toBeDisabled();
  });

  it('should call updatePreferences when save button is clicked', async () => {
    const mockUpdate = jest.fn().mockResolvedValue(undefined);
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      preferences: mockPreferences,
      updatePreferences: mockUpdate,
    });

    render(<RiskToleranceSettings />);

    // Make a change
    const positionBadge = screen.getByText('C');
    fireEvent.click(positionBadge);

    // Click save
    const saveButton = screen.getByText('Save Preferences');
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(mockUpdate).toHaveBeenCalledWith(
        expect.objectContaining({
          position_priorities: expect.arrayContaining(['SP', 'OF', 'C']),
        })
      );
    });
  });

  it('should call onSave callback when preferences are saved', async () => {
    const mockOnSave = jest.fn();
    const mockUpdate = jest.fn().mockResolvedValue(undefined);
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      preferences: mockPreferences,
      updatePreferences: mockUpdate,
    });

    render(<RiskToleranceSettings onSave={mockOnSave} />);

    // Make a change
    const positionBadge = screen.getByText('C');
    fireEvent.click(positionBadge);

    // Click save
    const saveButton = screen.getByText('Save Preferences');
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(mockOnSave).toHaveBeenCalled();
    });
  });

  it('should display success message after saving', async () => {
    const mockUpdate = jest.fn().mockResolvedValue(undefined);
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      preferences: mockPreferences,
      updatePreferences: mockUpdate,
    });

    render(<RiskToleranceSettings />);

    // Make a change
    const positionBadge = screen.getByText('C');
    fireEvent.click(positionBadge);

    // Click save
    const saveButton = screen.getByText('Save Preferences');
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(
        screen.getByText('Preferences saved successfully!')
      ).toBeInTheDocument();
    });
  });

  it('should reset form when reset button is clicked', () => {
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      preferences: mockPreferences,
    });

    render(<RiskToleranceSettings />);

    // Make a change - toggle position
    const positionC = screen.getByText('C');
    fireEvent.click(positionC);

    // C should now be selected (check Badge element has the blue class)
    expect(positionC).toHaveClass('bg-blue-600');

    // Click reset
    const resetButton = screen.getByText('Reset');
    fireEvent.click(resetButton);

    // C should no longer be selected
    expect(positionC).toHaveClass('bg-gray-100');
  });

  it('should toggle position priorities correctly', () => {
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      preferences: mockPreferences,
    });

    render(<RiskToleranceSettings />);

    // SP should be initially selected
    const spBadge = screen.getByText('SP');
    expect(spBadge).toHaveClass('bg-blue-600');

    // Click to deselect
    fireEvent.click(spBadge);
    expect(spBadge).toHaveClass('bg-gray-100');

    // Click to select again
    fireEvent.click(spBadge);
    expect(spBadge).toHaveClass('bg-blue-600');
  });

  it('should display error message when present', () => {
    const errorMessage = 'Failed to load preferences';
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      error: { ...defaultMockReturn.error, preferences: errorMessage },
    });

    render(<RiskToleranceSettings />);

    expect(screen.getByText(errorMessage)).toBeInTheDocument();
  });

  it('should display risk tolerance descriptions correctly', () => {
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      preferences: { ...mockPreferences, risk_tolerance: 'conservative' },
    });

    render(<RiskToleranceSettings />);

    expect(screen.getByText('Conservative')).toBeInTheDocument();
    expect(
      screen.getByText('Prioritize proven prospects with safer floors')
    ).toBeInTheDocument();
  });

  it('should display aggressive risk tolerance correctly', () => {
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      preferences: { ...mockPreferences, risk_tolerance: 'aggressive' },
    });

    render(<RiskToleranceSettings />);

    expect(screen.getByText('Aggressive')).toBeInTheDocument();
    expect(
      screen.getByText(
        'Focus on high-ceiling prospects with breakout potential'
      )
    ).toBeInTheDocument();
  });

  it('should handle checkbox toggles correctly', () => {
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      preferences: mockPreferences,
    });

    render(<RiskToleranceSettings />);

    // prefer_win_now should be checked
    const winNowCheckbox = screen.getByLabelText(
      /Prioritize win-now prospects/i
    );
    expect(winNowCheckbox).toBeChecked();

    // prefer_rebuild should be unchecked
    const rebuildCheckbox = screen.getByLabelText(
      /Prioritize rebuild prospects/i
    );
    expect(rebuildCheckbox).not.toBeChecked();

    // Toggle rebuild
    fireEvent.click(rebuildCheckbox);

    // Save button should now be enabled
    const saveButton = screen.getByText('Save Preferences');
    expect(saveButton).not.toBeDisabled();
  });

  it('should handle trade preference checkboxes correctly', () => {
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      preferences: mockPreferences,
    });

    render(<RiskToleranceSettings />);

    // prefer_buy_low should be checked
    const buyLowCheckbox = screen.getByLabelText(
      /Highlight buy-low opportunities/i
    );
    expect(buyLowCheckbox).toBeChecked();

    // prefer_sell_high should be unchecked
    const sellHighCheckbox = screen.getByLabelText(
      /Highlight sell-high opportunities/i
    );
    expect(sellHighCheckbox).not.toBeChecked();
  });

  it('should display all position options', () => {
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      preferences: mockPreferences,
    });

    render(<RiskToleranceSettings />);

    // Check all positions are displayed
    const positions = ['SP', 'RP', 'C', '1B', '2B', '3B', 'SS', 'OF', 'DH'];
    positions.forEach((position) => {
      expect(screen.getByText(position)).toBeInTheDocument();
    });
  });

  it('should disable buttons while saving', () => {
    const mockUpdate = jest.fn(() => new Promise(() => {})); // Never resolves
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      preferences: mockPreferences,
      updatePreferences: mockUpdate,
      loading: { ...defaultMockReturn.loading, preferences: true },
    });

    render(<RiskToleranceSettings />);

    // Make a change to enable buttons
    const positionBadge = screen.getByText('C');
    fireEvent.click(positionBadge);

    const saveButton = screen.getByText(/Saving.../i);
    expect(saveButton).toBeDisabled();
  });

  it('should handle save errors gracefully', async () => {
    const mockUpdate = jest.fn().mockRejectedValue(new Error('Network error'));
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      preferences: mockPreferences,
      updatePreferences: mockUpdate,
    });

    // Spy on console.error to verify it's called
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

    render(<RiskToleranceSettings />);

    // Make a change
    const positionBadge = screen.getByText('C');
    fireEvent.click(positionBadge);

    // Click save
    const saveButton = screen.getByText('Save Preferences');
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith(
        'Failed to save preferences:',
        expect.any(Error)
      );
    });

    consoleSpy.mockRestore();
  });

  it('should display info note about preferences', () => {
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      preferences: mockPreferences,
    });

    render(<RiskToleranceSettings />);

    expect(
      screen.getByText(
        /These preferences will be used to personalize your prospect recommendations/i
      )
    ).toBeInTheDocument();
  });

  it('should allow multiple position selections', () => {
    mockUseRecommendations.mockReturnValue({
      ...defaultMockReturn,
      preferences: {
        ...mockPreferences,
        position_priorities: [],
      },
    });

    render(<RiskToleranceSettings />);

    // Select multiple positions
    const sp = screen.getByText('SP');
    const of = screen.getByText('OF');
    const c = screen.getByText('C');

    fireEvent.click(sp);
    fireEvent.click(of);
    fireEvent.click(c);

    // All should be selected
    expect(sp).toHaveClass('bg-blue-600');
    expect(of).toHaveClass('bg-blue-600');
    expect(c).toHaveClass('bg-blue-600');
  });
});
