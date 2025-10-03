/**
 * React hook for managing email preferences state and operations.
 *
 * @hook useEmailPreferences
 * @module useEmailPreferences
 * @since 1.0.0
 */

import { useState, useEffect } from 'react';
import {
  getEmailPreferences,
  updateEmailPreferences,
  previewEmailDigest,
  EmailPreferences,
  EmailPreferencesUpdate,
  DigestPreview,
} from '@/lib/api/email';

/**
 * Return type for useEmailPreferences hook.
 *
 * @interface UseEmailPreferencesResult
 * @since 1.0.0
 */
export interface UseEmailPreferencesResult {
  /** Current email preferences */
  preferences: EmailPreferences | null;
  /** Loading state for initial fetch */
  isLoading: boolean;
  /** Error state */
  error: Error | null;
  /** Update loading state */
  isUpdating: boolean;
  /** Preview loading state */
  isPreviewing: boolean;
  /** Digest preview content */
  previewContent: DigestPreview | null;
  /** Update email preferences */
  updatePreferences: (updates: EmailPreferencesUpdate) => Promise<void>;
  /** Load digest preview */
  loadPreview: () => Promise<void>;
  /** Refresh preferences from server */
  refresh: () => Promise<void>;
}

/**
 * Custom hook for managing email preferences.
 *
 * Provides state management and operations for email digest settings
 * including loading, updating, and previewing digest content.
 *
 * @returns {UseEmailPreferencesResult} Email preferences state and operations
 *
 * @example
 * ```typescript
 * const {
 *   preferences,
 *   isLoading,
 *   updatePreferences,
 *   loadPreview
 * } = useEmailPreferences();
 *
 * // Update frequency
 * await updatePreferences({ frequency: 'daily' });
 *
 * // Preview digest
 * await loadPreview();
 * ```
 *
 * @since 1.0.0
 */
export function useEmailPreferences(): UseEmailPreferencesResult {
  const [preferences, setPreferences] = useState<EmailPreferences | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);
  const [isUpdating, setIsUpdating] = useState<boolean>(false);
  const [isPreviewing, setIsPreviewing] = useState<boolean>(false);
  const [previewContent, setPreviewContent] = useState<DigestPreview | null>(
    null
  );

  /**
   * Load email preferences from server.
   *
   * @since 1.0.0
   */
  const loadPreferences = async (): Promise<void> => {
    try {
      setIsLoading(true);
      setError(null);

      const data = await getEmailPreferences();
      setPreferences(data);
    } catch (err) {
      setError(
        err instanceof Error
          ? err
          : new Error('Failed to load email preferences')
      );
      console.error('Error loading email preferences:', err);
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Update email preferences.
   *
   * @param updates - Partial updates to apply
   * @throws {Error} If update fails
   *
   * @since 1.0.0
   */
  const updatePreferences = async (
    updates: EmailPreferencesUpdate
  ): Promise<void> => {
    try {
      setIsUpdating(true);
      setError(null);

      const updated = await updateEmailPreferences(updates);
      setPreferences(updated);
    } catch (err) {
      setError(
        err instanceof Error
          ? err
          : new Error('Failed to update email preferences')
      );
      console.error('Error updating email preferences:', err);
      throw err;
    } finally {
      setIsUpdating(false);
    }
  };

  /**
   * Load digest preview content.
   *
   * @throws {Error} If preview generation fails
   *
   * @since 1.0.0
   */
  const loadPreview = async (): Promise<void> => {
    try {
      setIsPreviewing(true);
      setError(null);

      const preview = await previewEmailDigest();
      setPreviewContent(preview);
    } catch (err) {
      setError(
        err instanceof Error ? err : new Error('Failed to load digest preview')
      );
      console.error('Error loading digest preview:', err);
      throw err;
    } finally {
      setIsPreviewing(false);
    }
  };

  /**
   * Refresh preferences from server.
   *
   * @since 1.0.0
   */
  const refresh = async (): Promise<void> => {
    await loadPreferences();
  };

  // Load preferences on mount
  useEffect(() => {
    loadPreferences();
  }, []);

  return {
    preferences,
    isLoading,
    error,
    isUpdating,
    isPreviewing,
    previewContent,
    updatePreferences,
    loadPreview,
    refresh,
  };
}
