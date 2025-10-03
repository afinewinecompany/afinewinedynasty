/**
 * Achievement API client functions.
 *
 * @fileoverview Client functions for achievement tracking and progress
 * @module achievements
 * @since 1.0.0
 */

import { apiClient } from './client';

/**
 * Achievement definition interface.
 *
 * @interface Achievement
 * @since 1.0.0
 */
export interface Achievement {
  id: string;
  name: string;
  description: string;
  criteria: string;
  icon: string;
  points: number;
  threshold?: number;
  unlocked?: boolean;
  unlocked_at?: string | null;
  progress?: number;
}

/**
 * Achievement progress summary interface.
 *
 * @interface AchievementProgress
 * @since 1.0.0
 */
export interface AchievementProgress {
  total_count: number;
  unlocked_count: number;
  total_points: number;
  earned_points: number;
  progress_percentage: number;
  next_achievement: Achievement | null;
  recent_unlocks: Achievement[];
}

/**
 * Get all available achievements.
 *
 * @returns Promise resolving to list of all achievements
 * @throws {Error} If API request fails
 *
 * @example
 * ```typescript
 * const achievements = await getAllAchievements();
 * console.log(`${achievements.length} total achievements`);
 * ```
 *
 * @since 1.0.0
 */
export async function getAllAchievements(): Promise<Achievement[]> {
  const response = await apiClient.get<Achievement[]>('/achievements/achievements');
  return response.data;
}

/**
 * Get current user's achievements.
 *
 * @param includeLocked - Include locked achievements with progress
 * @returns Promise resolving to user's achievements
 * @throws {Error} If API request fails
 *
 * @example
 * ```typescript
 * const { achievements } = await getUserAchievements(true);
 * const unlocked = achievements.filter(a => a.unlocked);
 * ```
 *
 * @since 1.0.0
 */
export async function getUserAchievements(
  includeLocked: boolean = false
): Promise<{ achievements: Achievement[]; total: number }> {
  const response = await apiClient.get<{ achievements: Achievement[]; total: number }>(
    '/achievements/users/achievements',
    { params: { include_locked: includeLocked } }
  );
  return response.data;
}

/**
 * Get current user's achievement progress summary.
 *
 * @returns Promise resolving to progress summary
 * @throws {Error} If API request fails
 *
 * @example
 * ```typescript
 * const progress = await getAchievementProgress();
 * console.log(`${progress.unlocked_count}/${progress.total_count} unlocked`);
 * console.log(`${progress.earned_points}/${progress.total_points} points`);
 * ```
 *
 * @since 1.0.0
 */
export async function getAchievementProgress(): Promise<AchievementProgress> {
  const response = await apiClient.get<AchievementProgress>(
    '/achievements/users/achievements/progress'
  );
  return response.data;
}
