/**
 * API client for onboarding operations
 *
 * Provides methods for interacting with onboarding endpoints including
 * starting, progressing, completing, and resetting onboarding flows.
 *
 * @module OnboardingAPI
 * @version 1.0.0
 * @author A Fine Wine Dynasty Team
 * @since 1.0.0
 */

import { apiClient } from './client';

/**
 * Onboarding status response interface
 *
 * @interface OnboardingStatus
 * @since 1.0.0
 */
export interface OnboardingStatus {
  user_id: number;
  current_step: number;
  current_step_name: string;
  total_steps: number;
  is_completed: boolean;
  progress_percentage: number;
  started_at: string | null;
  completed_at: string | null;
}

/**
 * Onboarding completion response interface
 *
 * @interface OnboardingCompletionResponse
 * @since 1.0.0
 */
export interface OnboardingCompletionResponse {
  user_id: number;
  is_completed: boolean;
  completed_at: string;
  message: string;
}

/**
 * Onboarding reset response interface
 *
 * @interface OnboardingResetResponse
 * @since 1.0.0
 */
export interface OnboardingResetResponse {
  user_id: number;
  current_step: number;
  is_completed: boolean;
  message: string;
}

/**
 * Start onboarding flow for current user
 *
 * @returns Promise resolving to onboarding status
 *
 * @throws {Error} When API request fails
 *
 * @example
 * ```typescript
 * const status = await startOnboarding();
 * console.log(status.current_step); // 0
 * ```
 *
 * @since 1.0.0
 */
export async function startOnboarding(): Promise<OnboardingStatus> {
  const response = await apiClient.post<OnboardingStatus>('/onboarding/start');
  return response.data;
}

/**
 * Get current onboarding status
 *
 * @returns Promise resolving to onboarding status
 *
 * @throws {Error} When API request fails
 *
 * @example
 * ```typescript
 * const status = await getOnboardingStatus();
 * console.log(`Step ${status.current_step} of ${status.total_steps}`);
 * ```
 *
 * @performance
 * - Typical response time: 10-30ms
 * - Cached on frontend for 30 seconds
 *
 * @since 1.0.0
 */
export async function getOnboardingStatus(): Promise<OnboardingStatus> {
  const response = await apiClient.get<OnboardingStatus>('/onboarding/status');
  return response.data;
}

/**
 * Progress to specified onboarding step
 *
 * @param step - Step number to progress to (0-indexed)
 * @returns Promise resolving to updated onboarding status
 *
 * @throws {Error} When step is invalid or API request fails
 *
 * @example
 * ```typescript
 * const status = await progressOnboarding(2);
 * console.log(status.current_step_name); // "feature_tour_profiles"
 * ```
 *
 * @since 1.0.0
 */
export async function progressOnboarding(
  step: number
): Promise<OnboardingStatus> {
  const response = await apiClient.post<OnboardingStatus>(
    '/onboarding/progress',
    { step }
  );
  return response.data;
}

/**
 * Complete onboarding flow
 *
 * @returns Promise resolving to completion response
 *
 * @throws {Error} When API request fails
 *
 * @example
 * ```typescript
 * const result = await completeOnboarding();
 * console.log(result.message); // "Onboarding completed successfully"
 * ```
 *
 * @since 1.0.0
 */
export async function completeOnboarding(): Promise<OnboardingCompletionResponse> {
  const response = await apiClient.post<OnboardingCompletionResponse>(
    '/onboarding/complete'
  );
  return response.data;
}

/**
 * Skip onboarding flow
 *
 * @returns Promise resolving to completion response
 *
 * @throws {Error} When API request fails
 *
 * @example
 * ```typescript
 * const result = await skipOnboarding();
 * console.log(result.is_completed); // true
 * ```
 *
 * @since 1.0.0
 */
export async function skipOnboarding(): Promise<OnboardingCompletionResponse> {
  const response =
    await apiClient.post<OnboardingCompletionResponse>('/onboarding/skip');
  return response.data;
}

/**
 * Reset onboarding progress
 *
 * @returns Promise resolving to reset response
 *
 * @throws {Error} When API request fails
 *
 * @example
 * ```typescript
 * const result = await resetOnboarding();
 * console.log(result.current_step); // 0
 * ```
 *
 * @since 1.0.0
 */
export async function resetOnboarding(): Promise<OnboardingResetResponse> {
  const response =
    await apiClient.post<OnboardingResetResponse>('/onboarding/reset');
  return response.data;
}
