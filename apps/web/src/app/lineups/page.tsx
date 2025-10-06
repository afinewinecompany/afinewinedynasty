'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/components/auth/AuthProvider';
import { lineupApi } from '@/lib/api-client';
import GoogleSignInButton from '@/components/auth/GoogleSignInButton';

interface Lineup {
  id: number;
  name: string;
  description?: string;
  lineup_type: string;
  prospect_count: number;
  created_at: string;
  updated_at: string;
}

export default function LineupsPage() {
  const router = useRouter();
  const { user, loading: authLoading, isAuthenticated } = useAuth();
  const [lineups, setLineups] = useState<Lineup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newLineupName, setNewLineupName] = useState('');
  const [creatingLineup, setCreatingLineup] = useState(false);

  useEffect(() => {
    if (!authLoading && isAuthenticated) {
      loadLineups();
    } else if (!authLoading && !isAuthenticated) {
      setLoading(false);
    }
  }, [authLoading, isAuthenticated]);

  const loadLineups = async () => {
    try {
      setLoading(true);
      const response: any = await lineupApi.getLineups();
      setLineups(response.lineups || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load lineups');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateLineup = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newLineupName.trim()) return;

    try {
      setCreatingLineup(true);
      await lineupApi.createLineup({
        name: newLineupName.trim(),
        lineup_type: 'custom',
      });
      setNewLineupName('');
      setShowCreateModal(false);
      await loadLineups();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to create lineup');
    } finally {
      setCreatingLineup(false);
    }
  };

  const handleDeleteLineup = async (lineupId: number, lineupName: string) => {
    if (!confirm(`Delete "${lineupName}"? This cannot be undone.`)) return;

    try {
      await lineupApi.deleteLineup(lineupId);
      await loadLineups();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to delete lineup');
    }
  };

  const getLineupTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      custom: 'Custom',
      fantrax_sync: 'Fantrax Sync',
      watchlist: 'Watchlist',
    };
    return labels[type] || type;
  };

  // Not authenticated
  if (!authLoading && !isAuthenticated) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
        <div className="max-w-md w-full bg-white rounded-lg shadow-md p-8 text-center">
          <h1 className="text-2xl font-bold text-gray-900 mb-4">
            Sign in to view your lineups
          </h1>
          <p className="text-gray-600 mb-6">
            Create and manage your prospect lineups with a free account
          </p>
          <GoogleSignInButton className="w-full" />
        </div>
      </div>
    );
  }

  // Loading
  if (authLoading || loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
          <p className="text-gray-600">Loading lineups...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">My Lineups</h1>
            <p className="text-gray-600 mt-1">
              Manage your prospect collections and lineups
            </p>
          </div>
          <button
            onClick={() => setShowCreateModal(true)}
            className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 transition-colors font-medium"
          >
            + Create Lineup
          </button>
        </div>

        {/* Error State */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
            <p className="text-red-800">{error}</p>
          </div>
        )}

        {/* Lineups Grid */}
        {lineups.length === 0 ? (
          <div className="bg-white rounded-lg shadow-sm p-12 text-center">
            <div className="max-w-md mx-auto">
              <div className="text-gray-400 mb-4">
                <svg
                  className="mx-auto h-16 w-16"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
              </div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">
                No lineups yet
              </h3>
              <p className="text-gray-600 mb-6">
                Create your first lineup to start tracking prospects
              </p>
              <button
                onClick={() => setShowCreateModal(true)}
                className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 transition-colors"
              >
                Create Your First Lineup
              </button>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {lineups.map((lineup) => (
              <div
                key={lineup.id}
                className="bg-white rounded-lg shadow-sm hover:shadow-md transition-shadow p-6 cursor-pointer"
                onClick={() => router.push(`/lineups/${lineup.id}`)}
              >
                <div className="flex justify-between items-start mb-4">
                  <h3 className="text-lg font-semibold text-gray-900">
                    {lineup.name}
                  </h3>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteLineup(lineup.id, lineup.name);
                    }}
                    className="text-gray-400 hover:text-red-600 transition-colors"
                  >
                    <svg
                      className="h-5 w-5"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                      />
                    </svg>
                  </button>
                </div>

                {lineup.description && (
                  <p className="text-gray-600 text-sm mb-4">
                    {lineup.description}
                  </p>
                )}

                <div className="flex items-center justify-between text-sm">
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                    {getLineupTypeLabel(lineup.lineup_type)}
                  </span>
                  <span className="text-gray-600">
                    {lineup.prospect_count || 0} prospects
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Create Lineup Modal */}
        {showCreateModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
              <h2 className="text-xl font-bold text-gray-900 mb-4">
                Create New Lineup
              </h2>
              <form onSubmit={handleCreateLineup}>
                <div className="mb-4">
                  <label
                    htmlFor="lineup-name"
                    className="block text-sm font-medium text-gray-700 mb-2"
                  >
                    Lineup Name
                  </label>
                  <input
                    id="lineup-name"
                    type="text"
                    value={newLineupName}
                    onChange={(e) => setNewLineupName(e.target.value)}
                    placeholder="e.g., My Top Prospects"
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    maxLength={100}
                    autoFocus
                  />
                </div>
                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={() => {
                      setShowCreateModal(false);
                      setNewLineupName('');
                    }}
                    className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={!newLineupName.trim() || creatingLineup}
                    className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {creatingLineup ? 'Creating...' : 'Create'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
