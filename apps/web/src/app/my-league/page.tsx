/**
 * My League Dashboard Page
 *
 * Provides a centralized dashboard for managing user's selected Fantrax leagues.
 * Features league selection dropdown and team-specific information display.
 *
 * @module app/my-league
 * @since 2.0.0
 */

'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { useAuth } from '@/hooks/useAuth';
import {
  getSecretAPILeagues,
  getSecretAPILeagueInfo,
  getSecretAPIRosters,
  getSecretAPIStandings,
  type SecretAPILeague,
  type LeagueInfoResponse,
  type RosterResponse,
  type StandingsResponse,
} from '@/lib/api/fantrax';
import {
  Trophy,
  Users,
  BarChart3,
  Activity,
  Crown,
  AlertCircle,
  Loader2,
  RefreshCw,
  ChevronRight,
} from 'lucide-react';

/**
 * My League Dashboard Page Component
 *
 * @returns Dashboard page for managing selected Fantrax leagues
 *
 * @since 2.0.0
 */
export default function MyLeaguePage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();

  // State management
  const [leagues, setLeagues] = useState<SecretAPILeague[]>([]);
  const [selectedLeagueId, setSelectedLeagueId] = useState<string>('');
  const [leagueInfo, setLeagueInfo] = useState<LeagueInfoResponse | null>(null);
  const [rosters, setRosters] = useState<RosterResponse | null>(null);
  const [standings, setStandings] = useState<StandingsResponse | null>(null);
  const [loading, setLoading] = useState({
    leagues: false,
    info: false,
    rosters: false,
    standings: false,
  });
  const [error, setError] = useState<string | null>(null);

  const isPremium = user?.subscriptionTier === 'premium';

  // Load active leagues on mount
  useEffect(() => {
    if (user && isPremium) {
      loadActiveLeagues();
    }
  }, [user, isPremium]);

  // Load league data when selection changes
  useEffect(() => {
    if (selectedLeagueId) {
      loadLeagueData(selectedLeagueId);
    }
  }, [selectedLeagueId]);

  /**
   * Load user's active leagues
   */
  const loadActiveLeagues = async () => {
    setLoading(prev => ({ ...prev, leagues: true }));
    setError(null);

    try {
      const allLeagues = await getSecretAPILeagues();
      // Filter to only active leagues
      const activeLeagues = allLeagues.filter(league => league.is_active);

      if (activeLeagues.length === 0) {
        setError('No leagues selected. Please go to Account Settings to select your leagues.');
      } else {
        setLeagues(activeLeagues);
        // Auto-select first league
        setSelectedLeagueId(activeLeagues[0].league_id);
      }
    } catch (err) {
      console.error('Failed to load leagues:', err);
      setError('Failed to load your leagues. Please check your Fantrax connection.');
    } finally {
      setLoading(prev => ({ ...prev, leagues: false }));
    }
  };

  /**
   * Load comprehensive league data
   */
  const loadLeagueData = async (leagueId: string) => {
    // Load league info
    setLoading(prev => ({ ...prev, info: true }));
    try {
      const info = await getSecretAPILeagueInfo(leagueId);
      setLeagueInfo(info);
    } catch (err) {
      console.error('Failed to load league info:', err);
    } finally {
      setLoading(prev => ({ ...prev, info: false }));
    }

    // Load rosters
    setLoading(prev => ({ ...prev, rosters: true }));
    try {
      const rostersData = await getSecretAPIRosters(leagueId);
      setRosters(rostersData);
    } catch (err) {
      console.error('Failed to load rosters:', err);
    } finally {
      setLoading(prev => ({ ...prev, rosters: false }));
    }

    // Load standings
    setLoading(prev => ({ ...prev, standings: true }));
    try {
      const standingsData = await getSecretAPIStandings(leagueId);
      setStandings(standingsData);
    } catch (err) {
      console.error('Failed to load standings:', err);
    } finally {
      setLoading(prev => ({ ...prev, standings: false }));
    }
  };

  /**
   * Handle refresh button click
   */
  const handleRefresh = () => {
    if (selectedLeagueId) {
      loadLeagueData(selectedLeagueId);
    }
  };

  // Loading state
  if (authLoading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="h-8 w-8 animate-spin" />
        </div>
      </div>
    );
  }

  // Not authenticated
  if (!user) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Card className="max-w-2xl mx-auto">
          <CardHeader>
            <CardTitle>Authentication Required</CardTitle>
            <CardDescription>
              Please log in to access your league dashboard.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={() => router.push('/login')}>
              Go to Login
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Premium gate
  if (!isPremium) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Card className="max-w-2xl mx-auto">
          <CardHeader>
            <div className="flex items-center gap-2">
              <Crown className="h-5 w-5 text-yellow-500" />
              <CardTitle>Premium Feature</CardTitle>
              <Badge variant="secondary">Premium</Badge>
            </div>
            <CardDescription>
              League management is a premium feature
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="p-6 bg-gradient-to-br from-yellow-50 to-orange-50 rounded-lg border-2 border-yellow-200">
              <h3 className="font-semibold text-lg mb-2">Upgrade to Premium</h3>
              <p className="text-sm text-muted-foreground mb-4">
                Get access to league management, personalized recommendations, and more.
              </p>
              <ul className="text-sm text-muted-foreground space-y-1 mb-4 list-disc list-inside">
                <li>Manage multiple dynasty leagues</li>
                <li>Real-time roster synchronization</li>
                <li>Team needs analysis</li>
                <li>Trade analyzer</li>
                <li>Personalized prospect recommendations</li>
              </ul>
              <Button onClick={() => router.push('/subscription')}>
                Upgrade Now - $9.99/month
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Main dashboard
  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-3xl font-bold">My League Dashboard</h1>
            <p className="text-muted-foreground mt-1">
              Manage your dynasty leagues and track team performance
            </p>
          </div>
          <div className="flex items-center gap-2">
            {selectedLeagueId && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleRefresh}
                disabled={loading.info || loading.rosters || loading.standings}
              >
                <RefreshCw className="h-4 w-4 mr-1" />
                Refresh
              </Button>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={() => router.push('/account?tab=fantrax')}
            >
              Manage Leagues
              <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </div>
        </div>

        {/* League Selector */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">Select League</CardTitle>
          </CardHeader>
          <CardContent>
            {loading.leagues ? (
              <Skeleton className="h-10 w-full" />
            ) : leagues.length > 0 ? (
              <Select
                value={selectedLeagueId}
                onValueChange={setSelectedLeagueId}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Choose a league" />
                </SelectTrigger>
                <SelectContent>
                  {leagues.map(league => (
                    <SelectItem key={league.league_id} value={league.league_id}>
                      <div className="flex items-center justify-between w-full">
                        <span>{league.name}</span>
                        {league.teams && league.teams.length > 0 && (
                          <span className="text-xs text-muted-foreground ml-2">
                            ({league.teams[0].team_name})
                          </span>
                        )}
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : (
              <Alert>
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                  {error || 'No leagues available. Please select leagues in Account Settings.'}
                </AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>
      </div>

      {/* League Content */}
      {selectedLeagueId && (
        <div className="space-y-6">
          {/* Quick Stats */}
          <div className="grid gap-4 md:grid-cols-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">League Rank</CardTitle>
                <Trophy className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {loading.standings ? (
                    <Skeleton className="h-8 w-16" />
                  ) : standings?.standings?.[0]?.rank ? (
                    `#${standings.standings[0].rank}`
                  ) : (
                    'N/A'
                  )}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Total Teams</CardTitle>
                <Users className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {loading.info ? (
                    <Skeleton className="h-8 w-16" />
                  ) : (
                    leagueInfo?.teams?.length || 0
                  )}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Season</CardTitle>
                <BarChart3 className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {loading.info ? (
                    <Skeleton className="h-8 w-16" />
                  ) : (
                    leagueInfo?.season || new Date().getFullYear()
                  )}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Period</CardTitle>
                <Activity className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {loading.info ? (
                    <Skeleton className="h-8 w-16" />
                  ) : (
                    `Week ${leagueInfo?.current_period || 1}`
                  )}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Detailed Information Tabs */}
          <Tabs defaultValue="standings" className="space-y-4">
            <TabsList>
              <TabsTrigger value="standings">Standings</TabsTrigger>
              <TabsTrigger value="roster">My Roster</TabsTrigger>
              <TabsTrigger value="matchups">Matchups</TabsTrigger>
              <TabsTrigger value="settings">League Settings</TabsTrigger>
            </TabsList>

            <TabsContent value="standings" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>League Standings</CardTitle>
                  <CardDescription>Current season standings</CardDescription>
                </CardHeader>
                <CardContent>
                  {loading.standings ? (
                    <div className="space-y-2">
                      {[1, 2, 3, 4, 5].map(i => (
                        <Skeleton key={i} className="h-12 w-full" />
                      ))}
                    </div>
                  ) : standings?.standings?.length ? (
                    <div className="overflow-x-auto">
                      <table className="w-full">
                        <thead>
                          <tr className="border-b">
                            <th className="text-left py-2">Rank</th>
                            <th className="text-left py-2">Team</th>
                            <th className="text-center py-2">W-L-T</th>
                            <th className="text-right py-2">Points</th>
                          </tr>
                        </thead>
                        <tbody>
                          {standings.standings.slice(0, 10).map((team: any, idx: number) => (
                            <tr key={idx} className="border-b">
                              <td className="py-2">{team.rank || idx + 1}</td>
                              <td className="py-2">{team.team_name || 'Team ' + (idx + 1)}</td>
                              <td className="text-center py-2">
                                {team.wins || 0}-{team.losses || 0}-{team.ties || 0}
                              </td>
                              <td className="text-right py-2">{team.points || 0}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="text-muted-foreground">No standings data available</p>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="roster" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>My Roster</CardTitle>
                  <CardDescription>Current team roster</CardDescription>
                </CardHeader>
                <CardContent>
                  {loading.rosters ? (
                    <div className="space-y-2">
                      {[1, 2, 3, 4, 5].map(i => (
                        <Skeleton key={i} className="h-12 w-full" />
                      ))}
                    </div>
                  ) : rosters?.rosters?.length ? (
                    <div className="space-y-4">
                      <p className="text-sm text-muted-foreground">
                        Roster data loaded for period {rosters.period}
                      </p>
                      <div className="grid gap-2">
                        {/* Would need to parse and display roster data based on actual structure */}
                        <p className="text-muted-foreground">
                          {rosters.rosters.length} roster(s) available
                        </p>
                      </div>
                    </div>
                  ) : (
                    <p className="text-muted-foreground">No roster data available</p>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="matchups" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Current Matchups</CardTitle>
                  <CardDescription>This week's matchups</CardDescription>
                </CardHeader>
                <CardContent>
                  {loading.info ? (
                    <div className="space-y-2">
                      {[1, 2, 3].map(i => (
                        <Skeleton key={i} className="h-20 w-full" />
                      ))}
                    </div>
                  ) : leagueInfo?.matchups?.length ? (
                    <div className="space-y-3">
                      {leagueInfo.matchups.slice(0, 6).map((matchup: any, idx: number) => (
                        <div key={idx} className="p-3 border rounded-lg">
                          <div className="flex justify-between items-center">
                            <span>{matchup.home_team || 'Home Team'}</span>
                            <span className="text-muted-foreground">vs</span>
                            <span>{matchup.away_team || 'Away Team'}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-muted-foreground">No matchup data available</p>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="settings" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>League Settings</CardTitle>
                  <CardDescription>Configuration and scoring settings</CardDescription>
                </CardHeader>
                <CardContent>
                  {loading.info ? (
                    <div className="space-y-2">
                      {[1, 2, 3, 4].map(i => (
                        <Skeleton key={i} className="h-8 w-full" />
                      ))}
                    </div>
                  ) : leagueInfo?.settings ? (
                    <div className="space-y-3">
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <p className="text-sm font-medium">League Name</p>
                          <p className="text-sm text-muted-foreground">{leagueInfo.name}</p>
                        </div>
                        <div>
                          <p className="text-sm font-medium">Sport</p>
                          <p className="text-sm text-muted-foreground">
                            {leagueInfo.sport || 'Baseball'}
                          </p>
                        </div>
                        <div>
                          <p className="text-sm font-medium">Season</p>
                          <p className="text-sm text-muted-foreground">{leagueInfo.season}</p>
                        </div>
                        <div>
                          <p className="text-sm font-medium">Current Period</p>
                          <p className="text-sm text-muted-foreground">
                            Week {leagueInfo.current_period}
                          </p>
                        </div>
                      </div>
                      {/* Would display more settings based on actual data structure */}
                    </div>
                  ) : (
                    <p className="text-muted-foreground">No settings data available</p>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      )}
    </div>
  );
}