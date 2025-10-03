/**
 * Custom hook for managing onboarding state and operations
 *
 * Provides state management and methods for onboarding flow including
 * progress tracking, step navigation, and completion handling.
 *
 * @hook useOnboarding
 * @version 1.0.0
 * @author A Fine Wine Dynasty Team
 * @since 1.0.0
 */

import { useState, useEffect, useCallback } from 'react';
import {
  OnboardingStatus,
  OnboardingCompletionResponse,
  startOnboarding,
  getOnboardingStatus,
  progressOnboarding,
  completeOnboarding,
  skipOnboarding,
  resetOnboarding
} from '@/lib/api/onboarding';

/**
 * Onboarding hook result interface
 *
 * @interface UseOnboardingResult
 * @since 1.0.0
 */
export interface UseOnboardingResult {
  /** Current onboarding status data */
  status: OnboardingStatus | null;
  /** Loading state for async operations */
  isLoading: boolean;
  /** Error state */
  error: Error | null;
  /** Start onboarding flow */
  start: () => Promise<void>;
  /** Progress to specific step */
  progressToStep: (step: number) => Promise<void>;
  /** Progress to next step */
  nextStep: () => Promise<void>;
  /** Progress to previous step */
  previousStep: () => Promise<void>;
  /** Complete onboarding */
  complete: () => Promise<void>;
  /** Skip onboarding */
  skip: () => Promise<void>;
  /** Reset onboarding */
  reset: () => Promise<void>;
  /** Refresh status */
  refresh: () => Promise<void>;
}

/**
 * Custom hook for managing user onboarding state and operations
 *
 * @param {boolean} autoLoad - Whether to automatically load status on mount (default: true)
 * @returns {UseOnboardingResult} Onboarding state and control functions
 *
 * @example
 * ```tsx
 * const {
 *   status,
 *   isLoading,
 *   error,
 *   nextStep,
 *   complete
 * } = useOnboarding();
 *
 * if (isLoading) return <LoadingSpinner />;
 * if (error) return <ErrorMessage error={error} />;
 * if (!status) return null;
 *
 * return (
 *   <OnboardingWizard
 *     currentStep={status.current_step}
 *     totalSteps={status.total_steps}
 *     onNext={nextStep}
 *     onComplete={complete}
 *   />
 * );
 * ```
 *
 * @since 1.0.0
 */
export function useOnboarding(autoLoad: boolean = true): UseOnboardingResult {
  const [status, setStatus] = useState<OnboardingStatus | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);

  /**
   * Load current onboarding status
   *
   * @returns Promise that resolves when status is loaded
   */
  const refresh = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getOnboardingStatus();
      setStatus(data);
    } catch (err) {
      setError(err as Error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * Start onboarding flow
   *
   * @returns Promise that resolves when onboarding is started
   */
  const start = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await startOnboarding();
      setStatus(data);
    } catch (err) {
      setError(err as Error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * Progress to specific step
   *
   * @param step - Step number to progress to
   * @returns Promise that resolves when step is updated
   */
  const progressToStep = useCallback(async (step: number): Promise<void> => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await progressOnboarding(step);
      setStatus(data);
    } catch (err) {
      setError(err as Error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * Progress to next step
   *
   * @returns Promise that resolves when next step is reached
   */
  const nextStep = useCallback(async (): Promise<void> => {
    if (!status) {
      setError(new Error('No onboarding status available'));
      return;
    }

    if (status.current_step >= status.total_steps - 1) {
      setError(new Error('Already at final step'));
      return;
    }

    await progressToStep(status.current_step + 1);
  }, [status, progressToStep]);

  /**
   * Progress to previous step
   *
   * @returns Promise that resolves when previous step is reached
   */
  const previousStep = useCallback(async (): Promise<void> => {
    if (!status) {
      setError(new Error('No onboarding status available'));
      return;
    }

    if (status.current_step <= 0) {
      setError(new Error('Already at first step'));
      return;
    }

    await progressToStep(status.current_step - 1);
  }, [status, progressToStep]);

  /**
   * Complete onboarding flow
   *
   * @returns Promise that resolves when onboarding is completed
   */
  const complete = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    setError(null);
    try {
      await completeOnboarding();
      // Refresh status to get updated completion data
      await refresh();
    } catch (err) {
      setError(err as Error);
    } finally {
      setIsLoading(false);
    }
  }, [refresh]);

  /**
   * Skip onboarding flow
   *
   * @returns Promise that resolves when onboarding is skipped
   */
  const skip = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    setError(null);
    try {
      await skipOnboarding();
      // Refresh status to get updated completion data
      await refresh();
    } catch (err) {
      setError(err as Error);
    } finally {
      setIsLoading(false);
    }
  }, [refresh]);

  /**
   * Reset onboarding progress
   *
   * @returns Promise that resolves when onboarding is reset
   */
  const reset = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    setError(null);
    try {
      await resetOnboarding();
      // Refresh status to get updated data
      await refresh();
    } catch (err) {
      setError(err as Error);
    } finally {
      setIsLoading(false);
    }
  }, [refresh]);

  // Auto-load status on mount if enabled
  useEffect(() => {
    if (autoLoad) {
      refresh();
    }
  }, [autoLoad, refresh]);

  return {
    status,
    isLoading,
    error,
    start,
    progressToStep,
    nextStep,
    previousStep,
    complete,
    skip,
    reset,
    refresh
  };
}
