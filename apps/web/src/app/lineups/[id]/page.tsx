'use client';

import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { useAuth } from '@/components/auth/AuthProvider';
import { lineupApi } from '@/lib/api-client';

interface Prospect {
  id: number;
  prospect_id: number;
  prospect_name: string;
  prospect_position: string;
  prospect_organization?: string;
  prospect_eta?: number;
  position?: string;
  rank?: number;
  notes?: string;
  added_at: string;
}

interface LineupDetail {
  id: number;
  name: string;
  description?: string;
  lineup_type: string;
  prospects: Prospect[];
  created_at: string;
  updated_at: string;
}

export default function LineupDetailPage() {
  const router = useRouter();
  const params = useParams();
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [lineup, setLineup] = useState<LineupDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const lineupId = params.id ? parseInt(params.id as string) : null;

  useEffect(() => {
    if (!authLoading) {
      if (!isAuthenticated) {
        router.push('/lineups');
      } else if (lineupId) {
        loadLineup();
      }
    }
  }, [authLoading, isAuthenticated, lineupId]);

  const loadLineup = async () => {
    if (!lineupId) return;

    try {
      setLoading(true);
      const data: any = await lineupApi.getLineup(lineupId);
      setLineup(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load lineup');
    } finally {
      setLoading(false);
    }
  };

  const handleRemoveProspect = async (prospectId: number, prospectName: string) => {
    if (!lineupId || !confirm(`Remove ${prospectName} from lineup?`)) return;

    try {
      await lineupApi.removeProspect(lineupId, prospectId);
      await loadLineup();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to remove prospect');
    }
  };

  const handleUpdateNotes = async (prospectId: number, notes: string) => {
    if (!lineupId) return;

    try {
      await lineupApi.updateProspect(lineupId, prospectId, { notes });
      await loadLineup();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to update notes');
    }
  };

  if (authLoading || loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
          <p className="text-gray-600">Loading lineup...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
        <div className="max-w-md w-full bg-white rounded-lg shadow-md p-8 text-center">
          <div className="text-red-600 mb-4">
            <svg
              className="mx-auto h-12 w-12"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Error Loading Lineup</h2>
          <p className="text-gray-600 mb-6">{error}</p>
          <button
            onClick={() => router.push('/lineups')}
            className="w-full bg-blue-600 text-white py-2 px-4 rounded-lg hover:bg-blue-700 transition-colors"
          >
            Back to Lineups
          </button>
        </div>
      </div>
    );
  }

  if (!lineup) {
    return null;
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <button
            onClick={() => router.push('/lineups')}
            className="text-blue-600 hover:text-blue-700 mb-4 flex items-center gap-2"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Back to Lineups
          </button>
          <h1 className="text-3xl font-bold text-gray-900">{lineup.name}</h1>
          {lineup.description && (
            <p className="text-gray-600 mt-2">{lineup.description}</p>
          )}
          <p className="text-sm text-gray-500 mt-2">
            {lineup.prospects.length} {lineup.prospects.length === 1 ? 'prospect' : 'prospects'}
          </p>
        </div>

        {/* Prospects List */}
        {lineup.prospects.length === 0 ? (
          <div className="bg-white rounded-lg shadow-sm p-12 text-center">
            <div className="max-w-md mx-auto">
              <div className="text-gray-400 mb-4">
                <svg className="mx-auto h-16 w-16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"
                  />
                </svg>
              </div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">No prospects yet</h3>
              <p className="text-gray-600">
                Browse prospects and add them to this lineup
              </p>
            </div>
          </div>
        ) : (
          <div className="bg-white rounded-lg shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Name
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Position
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Organization
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      ETA
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Notes
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {lineup.prospects.map((prospect) => (
                    <tr key={prospect.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm font-medium text-gray-900">
                          {prospect.prospect_name}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800">
                          {prospect.prospect_position}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                        {prospect.prospect_organization || '-'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                        {prospect.prospect_eta || '-'}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-600">
                        <div className="max-w-xs">
                          {prospect.notes ? (
                            <p className="truncate">{prospect.notes}</p>
                          ) : (
                            <span className="text-gray-400">No notes</span>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <button
                          onClick={() => handleRemoveProspect(prospect.prospect_id, prospect.prospect_name)}
                          className="text-red-600 hover:text-red-900"
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
