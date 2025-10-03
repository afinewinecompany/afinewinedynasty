/**
 * React hook for managing achievements state and operations.
 *
 * @hook useAchievements
 * @module useAchievements
 * @since 1.0.0
 */

import { useState, useEffect } from 'react';
import {
  getUserAchievements,
  getAchievementProgress,
  Achievement,
  AchievementProgress,
} from '@/lib/api/achievements';

/**
 * Return type for useAchievements hook.
 *
 * @interface UseAchievementsResult
 * @since 1.0.0
 */
export interface UseAchievementsResult {
  /** User's achievements list */
  achievements: Achievement[];
  /** Achievement progress summary */
  progress: AchievementProgress | null;
  /** Loading state */
  isLoading: boolean;
  /** Error state */
  error: Error | null;
  /** Refresh achievements from server */
  refresh: () => Promise<void>;
}

/**
 * Custom hook for managing user achievements.
 *
 * Provides state management for user's unlocked achievements and
 * overall progress tracking.
 *
 * @param includeLocked - Include locked achievements with progress info
 * @returns {UseAchievementsResult} Achievements state and operations
 *
 * @example
 * ```typescript
 * const {
 *   achievements,
 *   progress,
 *   isLoading
 * } = useAchievements(true);
 *
 * const unlocked = achievements.filter(a => a.unlocked);
 * console.log(`${progress?.earned_points} points earned`);
 * ```
 *
 * @since 1.0.0
 */
export function useAchievements(
  includeLocked: boolean = false
): UseAchievementsResult {
  const [achievements, setAchievements] = useState<Achievement[]>([]);
  const [progress, setProgress] = useState<AchievementProgress | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);

  /**
   * Load achievements and progress from server.
   *
   * @since 1.0.0
   */
  const loadAchievements = async (): Promise<void> => {
    try {
      setIsLoading(true);
      setError(null);

      // Load achievements and progress in parallel
      const [achievementsData, progressData] = await Promise.all([
        getUserAchievements(includeLocked),
        getAchievementProgress(),
      ]);

      setAchievements(achievementsData.achievements);
      setProgress(progressData);
    } catch (err) {
      setError(
        err instanceof Error ? err : new Error('Failed to load achievements')
      );
      console.error('Error loading achievements:', err);
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Refresh achievements from server.
   *
   * @since 1.0.0
   */
  const refresh = async (): Promise<void> => {
    await loadAchievements();
  };

  // Load achievements on mount and when includeLocked changes
  useEffect(() => {
    loadAchievements();
  }, [includeLocked]);

  return {
    achievements,
    progress,
    isLoading,
    error,
    refresh,
  };
}
