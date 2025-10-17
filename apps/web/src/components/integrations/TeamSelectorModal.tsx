/**
 * Team Selector Modal Component
 *
 * Allows users to manually select which team is theirs from a list
 * of teams in the league. This solves the issue where the automatic
 * team detection from Secret ID isn't working correctly.
 *
 * @component TeamSelectorModal
 * @since 1.0.0
 */

'use client';

import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Loader2, Users, CheckCircle } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import * as fantraxApi from '@/lib/api/fantrax';

/**
 * Component props
 */
interface TeamSelectorModalProps {
  /** Whether modal is open */
  isOpen: boolean;
  /** Callback when modal closes */
  onClose: () => void;
  /** League ID to fetch teams for */
  leagueId: string;
  /** League name for display */
  leagueName: string;
  /** Currently selected team ID (if any) */
  currentTeamId?: string;
  /** Callback when team is selected */
  onTeamSelected: (teamId: string, teamName: string) => Promise<void>;
}

/**
 * Team interface
 */
interface Team {
  team_id: string;
  team_name: string;
  owner_name?: string;
}

/**
 * Team selector modal for manually choosing user's team
 *
 * @param props - Component props
 * @returns Rendered modal component
 *
 * @example
 * ```tsx
 * <TeamSelectorModal
 *   isOpen={showTeamSelector}
 *   onClose={() => setShowTeamSelector(false)}
 *   leagueId={selectedLeague.league_id}
 *   leagueName={selectedLeague.league_name}
 *   onTeamSelected={handleTeamSelection}
 * />
 * ```
 *
 * @since 1.0.0
 */
export function TeamSelectorModal({
  isOpen,
  onClose,
  leagueId,
  leagueName,
  currentTeamId,
  onTeamSelected,
}: TeamSelectorModalProps): JSX.Element {
  const [teams, setTeams] = useState<Team[]>([]);
  const [selectedTeamId, setSelectedTeamId] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /**
   * Load teams when modal opens
   */
  useEffect(() => {
    if (isOpen && leagueId) {
      loadTeams();
    }
  }, [isOpen, leagueId]);

  /**
   * Fetch teams from the league
   */
  const loadTeams = async () => {
    setIsLoading(true);
    setError(null);

    try {
      // Get league info which includes all teams
      const leagueInfo = await fantraxApi.getSecretAPILeagueInfo(leagueId);

      if (leagueInfo.teams && Array.isArray(leagueInfo.teams)) {
        const teamList: Team[] = leagueInfo.teams.map((team: any) => ({
          team_id: team.id || team.team_id || team.teamId,
          team_name: team.name || team.team_name || team.teamName || 'Unknown Team',
          owner_name: team.owner || team.owner_name || team.ownerName,
        }));

        setTeams(teamList);

        // Pre-select current team if provided
        if (currentTeamId) {
          setSelectedTeamId(currentTeamId);
        }
      } else {
        setError('No teams found in this league');
      }
    } catch (err) {
      console.error('Failed to load teams:', err);
      setError('Failed to load teams. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Handle save button click
   */
  const handleSave = async () => {
    if (!selectedTeamId) {
      setError('Please select a team');
      return;
    }

    const selectedTeam = teams.find(t => t.team_id === selectedTeamId);
    if (!selectedTeam) {
      setError('Selected team not found');
      return;
    }

    setIsSaving(true);
    setError(null);

    try {
      await onTeamSelected(selectedTeam.team_id, selectedTeam.team_name);
      onClose();
    } catch (err) {
      console.error('Failed to save team selection:', err);
      setError('Failed to save team selection. Please try again.');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Users className="h-5 w-5" />
            Select Your Team
          </DialogTitle>
          <DialogDescription>
            Choose which team is yours in <strong>{leagueName}</strong>
          </DialogDescription>
        </DialogHeader>

        <div className="py-4">
          {isLoading && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin mr-2" />
              <span>Loading teams...</span>
            </div>
          )}

          {error && (
            <Alert variant="destructive" className="mb-4">
              <AlertTitle>Error</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {!isLoading && teams.length > 0 && (
            <div>
              <Label className="text-sm font-medium mb-3 block">
                Select the team you manage:
              </Label>
              <RadioGroup
                value={selectedTeamId}
                onValueChange={setSelectedTeamId}
                className="space-y-3 max-h-96 overflow-y-auto pr-2"
              >
                {teams.map((team) => (
                  <div
                    key={team.team_id}
                    className={`flex items-center space-x-3 p-3 rounded-lg border transition-colors hover:bg-gray-50 ${
                      selectedTeamId === team.team_id
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200'
                    }`}
                  >
                    <RadioGroupItem value={team.team_id} id={team.team_id} />
                    <Label
                      htmlFor={team.team_id}
                      className="flex-1 cursor-pointer"
                    >
                      <div className="font-medium">{team.team_name}</div>
                      {team.owner_name && (
                        <div className="text-sm text-gray-600">
                          Owner: {team.owner_name}
                        </div>
                      )}
                      <div className="text-xs text-gray-500 mt-1">
                        ID: {team.team_id}
                      </div>
                    </Label>
                    {currentTeamId === team.team_id && (
                      <CheckCircle className="h-5 w-5 text-green-600" />
                    )}
                  </div>
                ))}
              </RadioGroup>

              <Alert className="mt-4">
                <AlertDescription>
                  <strong>Tip:</strong> Select the team you manage in this league.
                  This will be saved and used for roster syncing and analysis.
                </AlertDescription>
              </Alert>
            </div>
          )}

          {!isLoading && teams.length === 0 && !error && (
            <Alert>
              <AlertTitle>No teams found</AlertTitle>
              <AlertDescription>
                No teams were found in this league. Please refresh and try again.
              </AlertDescription>
            </Alert>
          )}
        </div>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={onClose}
            disabled={isSaving}
          >
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            disabled={!selectedTeamId || isSaving}
          >
            {isSaving ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
                Saving...
              </>
            ) : (
              'Save Team Selection'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}