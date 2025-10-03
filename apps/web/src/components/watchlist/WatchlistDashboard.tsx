/**
 * Watchlist dashboard displaying all watched prospects
 *
 * @component WatchlistDashboard
 * @version 1.0.0
 * @since 1.0.0
 */

import React from 'react';
import { useWatchlist } from '@/hooks/useWatchlist';
import { WatchlistCard } from './WatchlistCard';

export const WatchlistDashboard: React.FC = () => {
  const { watchlist, isLoading, error, remove, updateNotes } = useWatchlist();

  if (isLoading) {
    return <div className="text-center py-8">Loading watchlist...</div>;
  }

  if (error) {
    return <div className="text-red-600">Error: {error.message}</div>;
  }

  if (watchlist.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        <p>Your watchlist is empty</p>
        <p className="text-sm mt-2">Add prospects to track their progress</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold">My Watchlist ({watchlist.length})</h2>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {watchlist.map((entry) => (
          <WatchlistCard
            key={entry.id}
            entry={entry}
            onRemove={remove}
            onUpdateNotes={updateNotes}
          />
        ))}
      </div>
    </div>
  );
};
