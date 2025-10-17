/**
 * Fantrax Integration Tab Component
 *
 * Manages Fantrax account connection, league selection, and roster syncing.
 * Provides in-browser authentication flow with real-time progress indicators.
 *
 * @component FantraxTab
 * @since 1.0.0
 */

'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { useFantrax } from '@/hooks/useFantrax';
import { useAuth } from '@/hooks/useAuth';
import { FantraxSecretIDModal } from '@/components/integrations/FantraxSecretIDModal';
import { TeamSelectorModal } from '@/components/integrations/TeamSelectorModal';
import { LeagueSelector } from '@/components/integrations/LeagueSelector';
import { RosterDisplay } from '@/components/integrations/RosterDisplay';
import { getSecretAPILeagues, updateLeagueSelections, updateTeamSelection } from '@/lib/api/fantrax';
import {
  CheckCircle2,
  XCircle,
  Loader2,
  Link as LinkIcon,
  RefreshCw,
  AlertCircle,
  Crown,
  Save,
  Settings,
} from 'lucide-react';

/**
 * Fantrax integration management tab
 *
 * @returns {JSX.Element} Rendered Fantrax integration interface
 *
 * @example
 * ```tsx
 * <FantraxTab />
 * ```
 *
 * @since 1.0.0
 */
export function FantraxTab(): JSX.Element {
  const { user } = useAuth();
  const {
    isConnected,
    leagues,
    selectedLeague,
    roster,
    loading,
    error,
    disconnect,
    refreshLeagues,
    selectLeague,
    syncRoster,
    checkConnection,
  } = useFantrax();

  const [showAuthModal, setShowAuthModal] = useState(false);
  const [showTeamSelector, setShowTeamSelector] = useState(false);
  const [selectedLeagueForTeam, setSelectedLeagueForTeam] = useState<any | null>(null);
  const [fantraxLeagues, setFantraxLeagues] = useState<any[]>([]);
  const [selectedLeagueIds, setSelectedLeagueIds] = useState<Set<string>>(new Set());
  const [loadingLeagues, setLoadingLeagues] = useState(false);
  const [savingSelections, setSavingSelections] = useState(false);
  const [leagueError, setLeagueError] = useState<string | null>(null);

  const isPremium = user?.subscriptionTier === 'premium';

  // Fetch leagues when connected
  useEffect(() => {
    if (isConnected) {
      fetchLeagues();
    }
  }, [isConnected]);

  /**
   * Fetch leagues from API
   */
  const fetchLeagues = async (): Promise<void> => {
    setLoadingLeagues(true);
    setLeagueError(null);
    try {
      const leagues = await getSecretAPILeagues();
      setFantraxLeagues(leagues);
      // Default to all leagues selected if none are active yet
      // Otherwise use the saved active state
      const hasAnyActive = leagues.some(l => l.is_active);
      const selected = new Set(
        hasAnyActive
          ? leagues.filter(l => l.is_active).map(l => l.league_id)
          : leagues.map(l => l.league_id) // Select all by default
      );
      setSelectedLeagueIds(selected);
    } catch (error) {
      setLeagueError('Failed to fetch leagues. Please try again.');
      console.error('Failed to fetch leagues:', error);
    } finally {
      setLoadingLeagues(false);
    }
  };

  /**
   * Handle league checkbox toggle
   */
  const handleLeagueToggle = (leagueId: string): void => {
    setSelectedLeagueIds(prev => {
      const newSet = new Set(prev);
      if (newSet.has(leagueId)) {
        newSet.delete(leagueId);
      } else {
        newSet.add(leagueId);
      }
      return newSet;
    });
  };

  /**
   * Save league selections
   */
  const handleSaveSelections = async (): Promise<void> => {
    setSavingSelections(true);
    setLeagueError(null);
    try {
      const response = await updateLeagueSelections(Array.from(selectedLeagueIds));
      if (response.success) {
        // Update local state to reflect saved selections
        setFantraxLeagues(prev =>
          prev.map(league => ({
            ...league,
            is_active: selectedLeagueIds.has(league.league_id),
          }))
        );
        // Show success message (you might want to use a toast here)
        alert(`Successfully saved ${response.selected_count} league selection(s)`);
      }
    } catch (error) {
      setLeagueError('Failed to save league selections. Please try again.');
      console.error('Failed to save selections:', error);
    } finally {
      setSavingSelections(false);
    }
  };

  /**
   * Handle successful authentication
   */
  const handleAuthSuccess = async (): Promise<void> => {
    setShowAuthModal(false);
    await checkConnection();
    await fetchLeagues(); // Fetch leagues after connecting
  };

  /**
   * Handle disconnect button click
   */
  const handleDisconnect = async (): Promise<void> => {
    if (confirm('Are you sure you want to disconnect your Fantrax account?')) {
      await disconnect();
      setFantraxLeagues([]);
      setSelectedLeagueIds(new Set());
    }
  };

  /**
   * Handle manual roster sync
   */
  const handleSync = async (): Promise<void> => {
    if (selectedLeague) {
      await syncRoster(false);
    }
  };

  /**
   * Open team selector for a league
   */
  const handleOpenTeamSelector = (league: any): void => {
    setSelectedLeagueForTeam(league);
    setShowTeamSelector(true);
  };

  /**
   * Handle team selection
   */
  const handleTeamSelection = async (teamId: string, teamName: string): Promise<void> => {
    if (!selectedLeagueForTeam) return;

    // Update the team selection in the backend
    await updateTeamSelection(selectedLeagueForTeam.league_id, teamId, teamName);

    // Update local state
    setFantraxLeagues(prev =>
      prev.map(league =>
        league.league_id === selectedLeagueForTeam.league_id
          ? { ...league, my_team_id: teamId, my_team_name: teamName }
          : league
      )
    );

    // Refresh leagues to get updated data from both sources
    await fetchLeagues();
    await refreshLeagues(); // Also refresh the useFantrax hook's leagues
  };

  // Premium gate
  if (!isPremium) {
    return (
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Crown className="h-5 w-5 text-yellow-500" />
            <CardTitle>Fantrax Integration</CardTitle>
            <Badge variant="secondary">Premium</Badge>
          </div>
          <CardDescription>
            Connect your Fantrax account to access personalized prospect recommendations
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="p-6 bg-gradient-to-br from-yellow-50 to-orange-50 rounded-lg border-2 border-yellow-200">
            <h3 className="font-semibold text-lg mb-2">Upgrade to Premium</h3>
            <p className="text-sm text-muted-foreground mb-4">
              Fantrax integration is a premium feature. Unlock personalized prospect
              recommendations based on your team needs.
            </p>
            <ul className="text-sm text-muted-foreground space-y-1 mb-4 list-disc list-inside">
              <li>Connect unlimited dynasty leagues</li>
              <li>Automatic roster sync</li>
              <li>Team needs analysis</li>
              <li>Personalized prospect recommendations</li>
            </ul>
            <Button className="w-full" onClick={() => window.location.href = '/subscription'}>
              Upgrade Now - $9.99/month
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Connection Status Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <LinkIcon className="h-5 w-5" />
            Fantrax Connection
          </CardTitle>
          <CardDescription>
            Connect your Fantrax account to sync your dynasty league rosters
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Connection Status Display */}
          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
            <div className="flex items-center gap-3">
              {isConnected ? (
                <>
                  <CheckCircle2 className="h-6 w-6 text-green-600" />
                  <div>
                    <p className="font-medium">Connected to Fantrax</p>
                    {leagues.length > 0 && (
                      <p className="text-sm text-gray-600">
                        {leagues.length} {leagues.length === 1 ? 'league' : 'leagues'} found
                      </p>
                    )}
                  </div>
                </>
              ) : (
                <>
                  <XCircle className="h-6 w-6 text-gray-400" />
                  <div>
                    <p className="font-medium">Not Connected</p>
                    <p className="text-sm text-gray-600">Connect to access your leagues</p>
                  </div>
                </>
              )}
            </div>

            {/* Action Buttons */}
            <div>
              {isConnected ? (
                <Button
                  variant="outline"
                  onClick={handleDisconnect}
                  disabled={loading.connection}
                >
                  {loading.connection ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Disconnecting...
                    </>
                  ) : (
                    'Disconnect'
                  )}
                </Button>
              ) : (
                <Button onClick={() => setShowAuthModal(true)} disabled={loading.connection}>
                  {loading.connection ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Connecting...
                    </>
                  ) : (
                    <>
                      <LinkIcon className="mr-2 h-4 w-4" />
                      Connect Fantrax
                    </>
                  )}
                </Button>
              )}
            </div>
          </div>

          {/* Error Display */}
          {error.connection && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error.connection}</AlertDescription>
            </Alert>
          )}

          {/* Connection Benefits (when disconnected) */}
          {!isConnected && (
            <>
              <div className="space-y-2 pt-4 border-t">
                <p className="font-medium text-sm">Benefits of connecting:</p>
                <ul className="text-sm text-gray-600 space-y-1 list-disc list-inside">
                  <li>Get prospect recommendations tailored to your team needs</li>
                  <li>Analyze your roster depth and identify future holes</li>
                  <li>Sync multiple dynasty leagues in one place</li>
                  <li>Track roster changes and league activity</li>
                </ul>
              </div>

            </>
          )}
        </CardContent>
      </Card>

      {/* League Selection (only when connected) */}
      {isConnected && (
        <Card>
          <CardHeader>
            <CardTitle>League Selection</CardTitle>
            <CardDescription>
              Choose which leagues you want to track in your dashboard
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {loadingLeagues ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin mr-2" />
                <span>Loading leagues...</span>
              </div>
            ) : fantraxLeagues.length > 0 ? (
              <>
                <div className="space-y-3">
                  {fantraxLeagues.map((league) => (
                    <div
                      key={league.league_id}
                      className="flex items-center space-x-3 p-3 rounded-lg border hover:bg-gray-50"
                    >
                      <Checkbox
                        id={league.league_id}
                        checked={selectedLeagueIds.has(league.league_id)}
                        onCheckedChange={(checked) => {
                          console.log('Checkbox changed:', league.league_id, checked);
                          handleLeagueToggle(league.league_id);
                        }}
                      />
                      <label
                        htmlFor={league.league_id}
                        className="flex-1 cursor-pointer"
                      >
                        <div>
                          <p className="font-medium">{league.name}</p>
                          {league.my_team_name ? (
                            <p className="text-sm text-muted-foreground">
                              Your Team: {league.my_team_name}
                            </p>
                          ) : league.teams && league.teams.length > 0 ? (
                            <p className="text-sm text-muted-foreground">
                              Team: {league.teams[0].team_name}
                            </p>
                          ) : (
                            <p className="text-sm text-orange-600">
                              No team selected - click to select your team
                            </p>
                          )}
                          {league.last_sync && league.roster_count ? (
                            <p className="text-xs text-green-600">
                              Synced: {league.roster_count} players • {new Date(league.last_sync).toLocaleDateString()}
                            </p>
                          ) : (
                            <p className="text-xs text-gray-500">
                              Not synced
                            </p>
                          )}
                        </div>
                      </label>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleOpenTeamSelector(league)}
                          className="h-8"
                        >
                          <Settings className="h-4 w-4 mr-1" />
                          {league.my_team_id ? 'Change Team' : 'Select Team'}
                        </Button>
                        {league.is_active && !selectedLeagueIds.has(league.league_id) && (
                          <Badge variant="outline" className="text-xs">
                            Currently Active
                          </Badge>
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Save button */}
                <div className="flex justify-between items-center pt-4 border-t">
                  <p className="text-sm text-muted-foreground">
                    {selectedLeagueIds.size} league{selectedLeagueIds.size !== 1 ? 's' : ''} selected
                  </p>
                  <Button
                    onClick={handleSaveSelections}
                    disabled={savingSelections}
                  >
                    {savingSelections ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Saving...
                      </>
                    ) : (
                      <>
                        <Save className="mr-2 h-4 w-4" />
                        Save Selection
                      </>
                    )}
                  </Button>
                </div>
              </>
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                No leagues found. Please make sure you're logged in to Fantrax.
              </div>
            )}

            {leagueError && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{leagueError}</AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>
      )}

      {/* League Management (only when connected and leagues selected) */}
      {isConnected && leagues.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>League Management</CardTitle>
            <CardDescription>Select a league to view roster and sync data</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <LeagueSelector
              leagues={leagues}
              selectedLeague={selectedLeague}
              onSelectLeague={selectLeague}
              isLoading={loading.leagues}
            />

            {selectedLeague && (
              <div className="flex items-center justify-between pt-4 border-t">
                <div>
                  <p className="text-sm font-medium">Roster Sync</p>
                  <p className="text-xs text-muted-foreground">
                    {roster?.last_sync
                      ? `Last synced: ${new Date(roster.last_sync).toLocaleString()}`
                      : 'Never synced'}
                  </p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleSync}
                  disabled={loading.sync}
                >
                  {loading.sync ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Syncing...
                    </>
                  ) : (
                    <>
                      <RefreshCw className="mr-2 h-4 w-4" />
                      Sync Roster
                    </>
                  )}
                </Button>
              </div>
            )}

            {error.sync && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error.sync}</AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>
      )}

      {/* Roster Display (when league selected and synced) */}
      {isConnected && selectedLeague && roster && (
        <RosterDisplay roster={roster} isLoading={loading.roster} />
      )}

      {/* Secret ID Authentication Modal */}
      <FantraxSecretIDModal
        isOpen={showAuthModal}
        onClose={() => setShowAuthModal(false)}
        onSuccess={handleAuthSuccess}
      />

      {/* Team Selector Modal */}
      {selectedLeagueForTeam && (
        <TeamSelectorModal
          isOpen={showTeamSelector}
          onClose={() => {
            setShowTeamSelector(false);
            setSelectedLeagueForTeam(null);
          }}
          leagueId={selectedLeagueForTeam.league_id}
          leagueName={selectedLeagueForTeam.name}
          currentTeamId={selectedLeagueForTeam.my_team_id}
          onTeamSelected={handleTeamSelection}
        />
      )}
    </div>
  );
}
