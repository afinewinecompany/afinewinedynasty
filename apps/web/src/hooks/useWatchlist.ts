/**
 * Custom hook for managing watchlist state and operations
 *
 * Provides state management and methods for prospect watchlist including
 * adding, removing, updating notes, and toggling notifications.
 *
 * @hook useWatchlist
 * @returns {UseWatchlistResult} Watchlist state and control functions
 *
 * @example
 * ```tsx
 * const {
 *   watchlist,
 *   isLoading,
 *   error,
 *   add,
 *   remove
 * } = useWatchlist();
 *
 * if (isLoading) return <LoadingSpinner />;
 * if (error) return <ErrorMessage error={error} />;
 *
 * return (
 *   <WatchlistDashboard
 *     entries={watchlist}
 *     onRemove={remove}
 *   />
 * );
 * ```
 *
 * @version 1.0.0
 * @since 1.0.0
 */

import { useState, useEffect, useCallback } from 'react';
import {
  WatchlistEntry,
  getWatchlist,
  addToWatchlist,
  removeFromWatchlist,
  updateWatchlistNotes,
  toggleWatchlistNotifications,
} from '@/lib/api/watchlist';

/**
 * Watchlist hook result interface
 *
 * @interface UseWatchlistResult
 * @since 1.0.0
 */
export interface UseWatchlistResult {
  /** Array of watchlist entries */
  watchlist: WatchlistEntry[];
  /** Loading state for async operations */
  isLoading: boolean;
  /** Error state */
  error: Error | null;
  /** Add prospect to watchlist */
  add: (prospectId: number, notes?: string) => Promise<void>;
  /** Remove prospect from watchlist */
  remove: (prospectId: number) => Promise<void>;
  /** Update notes for watchlist entry */
  updateNotes: (prospectId: number, notes: string) => Promise<void>;
  /** Toggle notifications for watchlist entry */
  toggleNotifications: (prospectId: number, enabled: boolean) => Promise<void>;
  /** Refresh watchlist data */
  refresh: () => Promise<void>;
}

/**
 * Custom hook for managing prospect watchlist
 *
 * @returns {UseWatchlistResult} Watchlist state and operations
 * @since 1.0.0
 */
export function useWatchlist(): UseWatchlistResult {
  const [watchlist, setWatchlist] = useState<WatchlistEntry[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getWatchlist();
      setWatchlist(data);
    } catch (err) {
      setError(err as Error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const add = useCallback(
    async (prospectId: number, notes?: string) => {
      try {
        await addToWatchlist(prospectId, notes);
        await refresh();
      } catch (err) {
        setError(err as Error);
        throw err;
      }
    },
    [refresh]
  );

  const remove = useCallback(
    async (prospectId: number) => {
      try {
        await removeFromWatchlist(prospectId);
        await refresh();
      } catch (err) {
        setError(err as Error);
        throw err;
      }
    },
    [refresh]
  );

  const updateNotes = useCallback(
    async (prospectId: number, notes: string) => {
      try {
        await updateWatchlistNotes(prospectId, notes);
        await refresh();
      } catch (err) {
        setError(err as Error);
        throw err;
      }
    },
    [refresh]
  );

  const toggleNotifications = useCallback(
    async (prospectId: number, enabled: boolean) => {
      try {
        await toggleWatchlistNotifications(prospectId, enabled);
        await refresh();
      } catch (err) {
        setError(err as Error);
        throw err;
      }
    },
    [refresh]
  );

  useEffect(() => {
    refresh();
  }, [refresh]);

  return {
    watchlist,
    isLoading,
    error,
    add,
    remove,
    updateNotes,
    toggleNotifications,
    refresh,
  };
}
