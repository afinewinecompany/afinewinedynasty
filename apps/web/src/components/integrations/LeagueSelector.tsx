/**
 * League Selector Component
 *
 * Displays user's Fantrax leagues and allows selection for analysis and recommendations.
 *
 * @component LeagueSelector
 * @since 1.0.0
 */

'use client';

import React from 'react';
import { useFantrax } from '@/hooks/useFantrax';
import type { FantraxLeague } from '@/types/fantrax';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, Users, Trophy, RefreshCw } from 'lucide-react';

/**
 * Component props
 */
interface LeagueSelectorProps {
  /** Optional callback when league is selected */
  onLeagueSelect?: (league: FantraxLeague) => void;
  /** Whether to auto-load roster on selection */
  autoLoadRoster?: boolean;
  /** Optional explicit leagues list (overrides hook) */
  leagues?: FantraxLeague[];
  /** Optional explicit selected league (overrides hook) */
  selectedLeague?: FantraxLeague | null;
  /** Optional explicit onSelectLeague handler (overrides hook) */
  onSelectLeague?: (league: FantraxLeague) => void;
  /** Optional explicit loading state (overrides hook) */
  isLoading?: boolean;
}

/**
 * League selector component for multi-league support
 *
 * @param props - Component props
 * @returns Rendered component
 *
 * @example
 * ```tsx
 * <LeagueSelector
 *   onLeagueSelect={(league) => console.log('Selected:', league.league_name)}
 *   autoLoadRoster={true}
 * />
 * ```
 *
 * @since 1.0.0
 */
export function LeagueSelector({
  onLeagueSelect,
  autoLoadRoster = false,
  leagues: leaguesProp,
  selectedLeague: selectedLeagueProp,
  onSelectLeague: onSelectLeagueProp,
  isLoading: isLoadingProp,
}: LeagueSelectorProps) {
  const hookData = useFantrax();

  // Use props if provided, otherwise fall back to hook
  const leagues = leaguesProp ?? hookData.leagues;
  const selectedLeague = selectedLeagueProp !== undefined ? selectedLeagueProp : hookData.selectedLeague;
  const loading = isLoadingProp !== undefined ? { leagues: isLoadingProp, sync: false } : hookData.loading;
  const error = hookData.error;
  const selectLeague = onSelectLeagueProp ?? hookData.selectLeague;
  const refreshLeagues = hookData.refreshLeagues;
  const syncRoster = hookData.syncRoster;

  /**
   * Handle league selection
   */
  const handleSelect = async (league: FantraxLeague) => {
    selectLeague(league);
    onLeagueSelect?.(league);

    // Auto-load roster if enabled
    if (autoLoadRoster) {
      await syncRoster();
    }
  };

  /**
   * Get league type badge color
   */
  const getLeagueTypeBadge = (type: string) => {
    const colors = {
      dynasty: 'bg-purple-100 text-purple-800',
      keeper: 'bg-blue-100 text-blue-800',
      redraft: 'bg-gray-100 text-gray-800',
    };
    return colors[type as keyof typeof colors] || colors.redraft;
  };

  /**
   * Format last sync time
   */
  const formatLastSync = (lastSync?: string) => {
    if (!lastSync) return 'Never synced';

    const date = new Date(lastSync);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} min ago`;

    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24)
      return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;

    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
  };

  if (loading.leagues) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
          <span className="ml-2 text-gray-600">Loading leagues...</span>
        </CardContent>
      </Card>
    );
  }

  if (error.leagues) {
    return (
      <Card>
        <CardContent className="py-6">
          <Alert variant="destructive">
            <AlertDescription>{error.leagues}</AlertDescription>
          </Alert>
          <Button onClick={refreshLeagues} className="mt-4">
            Try Again
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (leagues.length === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <Trophy className="h-12 w-12 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-600 mb-2">No leagues found</p>
          <p className="text-sm text-gray-500 mb-4">
            Make sure you have active leagues in your Fantrax account
          </p>
          <Button onClick={refreshLeagues} variant="outline">
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh Leagues
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Your Fantrax Leagues</CardTitle>
            <CardDescription>
              Select a league to view roster analysis and recommendations
            </CardDescription>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={refreshLeagues}
            disabled={loading.leagues}
          >
            <RefreshCw
              className={`h-4 w-4 ${loading.leagues ? 'animate-spin' : ''}`}
            />
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {leagues.map((league) => {
            const isSelected = selectedLeague?.league_id === league.league_id;

            return (
              <button
                key={league.league_id}
                onClick={() => handleSelect(league)}
                className={`w-full text-left p-4 rounded-lg border-2 transition-all hover:shadow-md ${
                  isSelected
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <h3 className="font-semibold text-gray-900">
                        {league.league_name}
                      </h3>
                      <Badge className={getLeagueTypeBadge(league.league_type)}>
                        {league.league_type}
                      </Badge>
                      {!league.is_active && (
                        <Badge variant="secondary">Inactive</Badge>
                      )}
                    </div>

                    <div className="flex items-center gap-4 text-sm text-gray-600">
                      <div className="flex items-center gap-1">
                        <Users className="h-4 w-4" />
                        <span>{league.team_count} teams</span>
                      </div>
                      <div>
                        <span>{league.roster_size} roster spots</span>
                      </div>
                      <div>
                        <span className="text-xs text-gray-500">
                          Last sync: {formatLastSync(league.last_sync)}
                        </span>
                      </div>
                    </div>

                    <div className="mt-2 text-xs text-gray-500">
                      {league.scoring_type}
                    </div>
                  </div>

                  {isSelected && (
                    <div className="ml-4">
                      <div className="h-6 w-6 rounded-full bg-blue-500 flex items-center justify-center">
                        <svg
                          className="h-4 w-4 text-white"
                          fill="none"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth="2"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path d="M5 13l4 4L19 7"></path>
                        </svg>
                      </div>
                    </div>
                  )}
                </div>
              </button>
            );
          })}
        </div>

        {selectedLeague && (
          <div className="mt-4 pt-4 border-t">
            <Button
              onClick={() => syncRoster(true)}
              disabled={loading.sync}
              variant="outline"
              className="w-full"
            >
              {loading.sync ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Syncing roster...
                </>
              ) : (
                <>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Sync {selectedLeague.league_name} Roster
                </>
              )}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
