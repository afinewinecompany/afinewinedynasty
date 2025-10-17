/**
 * Roster Display Component
 *
 * Displays synced Fantrax roster with player details, positions, and status.
 * Shows roster composition analysis and depth breakdown.
 *
 * @component RosterDisplay
 * @since 1.0.0
 */

'use client';

import React, { useState } from 'react';
import type { RosterData, RosterPlayer } from '@/types/fantrax';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Loader2, Users, TrendingUp, TrendingDown } from 'lucide-react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

/**
 * Component props
 */
interface RosterDisplayProps {
  /** Roster data to display */
  roster: RosterData;
  /** Whether roster is currently loading */
  isLoading?: boolean;
}

/**
 * Roster display component showing team composition
 *
 * @param props - Component props
 * @returns Rendered component
 *
 * @example
 * ```tsx
 * <RosterDisplay
 *   roster={rosterData}
 *   isLoading={false}
 * />
 * ```
 *
 * @since 1.0.0
 */
export function RosterDisplay({
  roster,
  isLoading = false,
}: RosterDisplayProps): JSX.Element {
  const [sortBy, setSortBy] = useState<'name' | 'position' | 'age'>('name');
  const [filterPosition, setFilterPosition] = useState<string | null>(null);

  /**
   * Get player status badge color
   */
  const getStatusBadge = (status: RosterPlayer['status']) => {
    const variants = {
      active: 'bg-green-100 text-green-800',
      injured: 'bg-red-100 text-red-800',
      minors: 'bg-blue-100 text-blue-800',
      suspended: 'bg-orange-100 text-orange-800',
      il: 'bg-red-100 text-red-800',
    };
    return variants[status] || 'bg-gray-100 text-gray-800';
  };

  /**
   * Get position badge color
   */
  const getPositionColor = (position: string) => {
    const colors: Record<string, string> = {
      C: 'bg-purple-100 text-purple-800',
      '1B': 'bg-blue-100 text-blue-800',
      '2B': 'bg-blue-100 text-blue-800',
      '3B': 'bg-blue-100 text-blue-800',
      SS: 'bg-blue-100 text-blue-800',
      OF: 'bg-green-100 text-green-800',
      DH: 'bg-gray-100 text-gray-800',
      SP: 'bg-orange-100 text-orange-800',
      RP: 'bg-red-100 text-red-800',
    };
    return colors[position] || 'bg-gray-100 text-gray-800';
  };

  /**
   * Calculate position depth breakdown
   */
  const getPositionBreakdown = () => {
    const breakdown: Record<string, number> = {};
    if (!roster.players || !Array.isArray(roster.players)) {
      return breakdown;
    }
    roster.players.forEach((player) => {
      if (player.positions && Array.isArray(player.positions)) {
        player.positions.forEach((pos) => {
          breakdown[pos] = (breakdown[pos] || 0) + 1;
        });
      }
    });
    return breakdown;
  };

  /**
   * Calculate roster statistics
   */
  const getRosterStats = () => {
    if (!roster.players || !Array.isArray(roster.players)) {
      return { total: 0, active: 0, minors: 0, avgAge: '0.0' };
    }

    const totalPlayers = roster.players.length;
    const activePlayers = roster.players.filter((p) => p.status === 'active').length;
    const minorsPlayers = roster.players.filter((p) => p.minor_league_eligible).length;
    const playersWithAge = roster.players.filter((p) => p.age);
    const avgAge = playersWithAge.length > 0
      ? playersWithAge.reduce((sum, p) => sum + (p.age || 0), 0) / playersWithAge.length
      : 0;

    return {
      total: totalPlayers,
      active: activePlayers,
      minors: minorsPlayers,
      avgAge: avgAge.toFixed(1),
    };
  };

  /**
   * Sort and filter players
   */
  const getSortedPlayers = () => {
    if (!roster.players || !Array.isArray(roster.players)) {
      return [];
    }

    let filtered = [...roster.players];

    // Apply position filter
    if (filterPosition) {
      filtered = filtered.filter((p) =>
        p.positions && Array.isArray(p.positions) && p.positions.includes(filterPosition)
      );
    }

    // Apply sorting
    filtered.sort((a, b) => {
      switch (sortBy) {
        case 'name':
          return (a.player_name || '').localeCompare(b.player_name || '');
        case 'position':
          const aPos = a.positions && a.positions[0] ? a.positions[0] : '';
          const bPos = b.positions && b.positions[0] ? b.positions[0] : '';
          return aPos.localeCompare(bPos);
        case 'age':
          return (a.age || 0) - (b.age || 0);
        default:
          return 0;
      }
    });

    return filtered;
  };

  const positionBreakdown = getPositionBreakdown();
  const stats = getRosterStats();
  const sortedPlayers = getSortedPlayers();

  if (isLoading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
          <span className="ml-2 text-gray-600">Loading roster...</span>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Roster Overview Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="h-5 w-5" />
            {roster.team_name} Roster
          </CardTitle>
          <CardDescription>
            Last synced: {new Date(roster.last_updated).toLocaleString()}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* Roster Statistics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="p-4 bg-blue-50 rounded-lg">
              <p className="text-sm text-gray-600 mb-1">Total Players</p>
              <p className="text-2xl font-bold text-blue-900">{stats.total}</p>
            </div>
            <div className="p-4 bg-green-50 rounded-lg">
              <p className="text-sm text-gray-600 mb-1">Active</p>
              <p className="text-2xl font-bold text-green-900">{stats.active}</p>
            </div>
            <div className="p-4 bg-purple-50 rounded-lg">
              <p className="text-sm text-gray-600 mb-1">Minor League</p>
              <p className="text-2xl font-bold text-purple-900">{stats.minors}</p>
            </div>
            <div className="p-4 bg-orange-50 rounded-lg">
              <p className="text-sm text-gray-600 mb-1">Average Age</p>
              <p className="text-2xl font-bold text-orange-900">{stats.avgAge}</p>
            </div>
          </div>

          {/* Position Breakdown */}
          <div className="border-t pt-4">
            <h3 className="font-semibold mb-3">Position Depth</h3>
            <div className="flex flex-wrap gap-2">
              {Object.entries(positionBreakdown)
                .sort(([, a], [, b]) => b - a)
                .map(([position, count]) => (
                  <button
                    key={position}
                    onClick={() =>
                      setFilterPosition(filterPosition === position ? null : position)
                    }
                    className={`px-3 py-1 rounded-full text-sm font-medium transition-all ${
                      filterPosition === position
                        ? 'ring-2 ring-blue-500 ring-offset-2'
                        : ''
                    } ${getPositionColor(position)}`}
                  >
                    {position} ({count})
                  </button>
                ))}
            </div>
            {filterPosition && (
              <button
                onClick={() => setFilterPosition(null)}
                className="text-sm text-blue-600 hover:text-blue-800 mt-2"
              >
                Clear filter
              </button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Roster Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Players</CardTitle>
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-600">Sort by:</span>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
                className="text-sm border rounded px-2 py-1"
              >
                <option value="name">Name</option>
                <option value="position">Position</option>
                <option value="age">Age</option>
              </select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Player</TableHead>
                  <TableHead>Positions</TableHead>
                  <TableHead>Team</TableHead>
                  <TableHead>Age</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Contract</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sortedPlayers.map((player) => (
                  <TableRow key={player.player_id}>
                    <TableCell className="font-medium">
                      {player.player_name}
                      {player.minor_league_eligible && (
                        <Badge
                          variant="secondary"
                          className="ml-2 text-xs bg-blue-100 text-blue-800"
                        >
                          MiLB
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        {player.positions && Array.isArray(player.positions) ? (
                          player.positions.map((pos) => (
                            <Badge
                              key={pos}
                              className={`text-xs ${getPositionColor(pos)}`}
                            >
                              {pos}
                            </Badge>
                          ))
                        ) : (
                          <span className="text-gray-400">-</span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>{player.team}</TableCell>
                    <TableCell>{player.age || '-'}</TableCell>
                    <TableCell>
                      <Badge className={getStatusBadge(player.status)}>
                        {player.status}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {player.contract_years ? (
                        <span className="text-sm">
                          {player.contract_years}yr
                          {player.contract_value && ` / $${player.contract_value}M`}
                        </span>
                      ) : (
                        '-'
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {sortedPlayers.length === 0 && (
            <div className="text-center py-8 text-gray-500">
              No players found
              {filterPosition && ` for position ${filterPosition}`}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
