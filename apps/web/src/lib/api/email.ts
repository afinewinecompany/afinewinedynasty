/**
 * Email preferences API client functions.
 *
 * @fileoverview Client functions for email digest and preference management
 * @module email
 * @since 1.0.0
 */

import { apiClient } from './client';

/**
 * Email preference settings interface.
 *
 * @interface EmailPreferences
 * @since 1.0.0
 */
export interface EmailPreferences {
  id: number;
  user_id: number;
  digest_enabled: boolean;
  frequency: 'daily' | 'weekly' | 'monthly';
  preferences: Record<string, any>;
  last_sent: string | null;
  created_at: string;
  updated_at: string;
}

/**
 * Email preferences update payload.
 *
 * @interface EmailPreferencesUpdate
 * @since 1.0.0
 */
export interface EmailPreferencesUpdate {
  digest_enabled?: boolean;
  frequency?: 'daily' | 'weekly' | 'monthly';
  preferences?: Record<string, any>;
}

/**
 * Digest content preview interface.
 *
 * @interface DigestPreview
 * @since 1.0.0
 */
export interface DigestPreview {
  message: string;
  content: {
    user_name: string;
    user_email: string;
    watchlist_updates: any[];
    top_movers: any[];
    recommendations: any[];
    achievement_progress: any;
    generated_at: string;
  } | null;
}

/**
 * Get current user's email preferences.
 *
 * @returns Promise resolving to email preferences object
 * @throws {Error} If API request fails
 *
 * @example
 * ```typescript
 * const prefs = await getEmailPreferences();
 * console.log(prefs.frequency); // "weekly"
 * ```
 *
 * @since 1.0.0
 */
export async function getEmailPreferences(): Promise<EmailPreferences> {
  const response = await apiClient.get<EmailPreferences>('/users/email-preferences');
  return response.data;
}

/**
 * Update current user's email preferences.
 *
 * @param updates - Partial updates to email preferences
 * @returns Promise resolving to updated preferences object
 * @throws {Error} If API request fails or validation fails
 *
 * @example
 * ```typescript
 * const updated = await updateEmailPreferences({
 *   digest_enabled: false,
 *   frequency: 'monthly'
 * });
 * ```
 *
 * @since 1.0.0
 */
export async function updateEmailPreferences(
  updates: EmailPreferencesUpdate
): Promise<EmailPreferences> {
  const response = await apiClient.put<EmailPreferences>(
    '/users/email-preferences',
    updates
  );
  return response.data;
}

/**
 * Unsubscribe from email digests using token.
 *
 * @param token - Unsubscribe token from email link
 * @returns Promise resolving to success response
 * @throws {Error} If token invalid or request fails
 *
 * @example
 * ```typescript
 * const result = await unsubscribeFromDigest(token);
 * console.log(result.message); // "Successfully unsubscribed"
 * ```
 *
 * @since 1.0.0
 */
export async function unsubscribeFromDigest(token: string): Promise<{
  success: boolean;
  message: string;
}> {
  const response = await apiClient.post('/users/unsubscribe', { token });
  return response.data;
}

/**
 * Preview email digest content without sending.
 *
 * Useful for showing users what their weekly digest will look like.
 *
 * @returns Promise resolving to digest preview content
 * @throws {Error} If API request fails
 *
 * @example
 * ```typescript
 * const preview = await previewEmailDigest();
 * if (preview.content) {
 *   console.log(`${preview.content.watchlist_updates.length} updates`);
 * }
 * ```
 *
 * @since 1.0.0
 */
export async function previewEmailDigest(): Promise<DigestPreview> {
  const response = await apiClient.get<DigestPreview>('/users/preview-digest');
  return response.data;
}
