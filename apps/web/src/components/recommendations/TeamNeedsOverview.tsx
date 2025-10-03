/**
 * Team Needs Overview Component
 *
 * Displays team needs analysis including positional gaps, depth analysis,
 * competitive window, and future roster projections.
 *
 * @component TeamNeedsOverview
 * @since 1.0.0
 */

'use client';

import React, { useEffect } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Loader2,
  TrendingUp,
  AlertTriangle,
  Users,
  Calendar,
} from 'lucide-react';
import { useRecommendations } from '@/hooks/useRecommendations';
import type { PositionalNeed, DepthAnalysis } from '@/types/recommendations';

/**
 * Component props
 */
interface TeamNeedsOverviewProps {
  /** Fantrax league ID */
  leagueId: string;
  /** Whether to auto-load data on mount */
  autoLoad?: boolean;
  /** Optional callback when refresh is triggered */
  onRefresh?: () => void;
}

/**
 * Team needs overview component
 *
 * @param props - Component props
 * @returns Rendered component
 *
 * @example
 * ```tsx
 * <TeamNeedsOverview
 *   leagueId="abc123"
 *   autoLoad={true}
 * />
 * ```
 *
 * @since 1.0.0
 */
export function TeamNeedsOverview({
  leagueId,
  autoLoad = true,
  onRefresh,
}: TeamNeedsOverviewProps) {
  const { teamNeeds, loading, error, fetchTeamNeeds } = useRecommendations();

  // Auto-load on mount
  useEffect(() => {
    if (autoLoad && leagueId) {
      fetchTeamNeeds(leagueId);
    }
  }, [autoLoad, leagueId, fetchTeamNeeds]);

  /**
   * Get severity badge color
   */
  const getSeverityColor = (severity: PositionalNeed['severity']): string => {
    const colors = {
      critical: 'bg-red-100 text-red-800',
      high: 'bg-orange-100 text-orange-800',
      medium: 'bg-yellow-100 text-yellow-800',
      low: 'bg-blue-100 text-blue-800',
    };
    return colors[severity];
  };

  /**
   * Get competitive window badge color
   */
  const getWindowColor = (window: string): string => {
    const colors = {
      contending: 'bg-green-100 text-green-800',
      transitional: 'bg-yellow-100 text-yellow-800',
      rebuilding: 'bg-orange-100 text-orange-800',
    };
    return colors[window as keyof typeof colors] || colors.transitional;
  };

  /**
   * Get depth gap severity indicator
   */
  const getGapIndicator = (gapScore: number) => {
    if (gapScore >= 70) return { color: 'text-red-600', label: 'Critical Gap' };
    if (gapScore >= 50)
      return { color: 'text-orange-600', label: 'Significant Gap' };
    if (gapScore >= 30) return { color: 'text-yellow-600', label: 'Minor Gap' };
    return { color: 'text-green-600', label: 'Adequate' };
  };

  /**
   * Handle refresh
   */
  const handleRefresh = () => {
    fetchTeamNeeds(leagueId);
    onRefresh?.();
  };

  if (loading.teamNeeds) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
          <span className="ml-2 text-gray-600">Analyzing team needs...</span>
        </CardContent>
      </Card>
    );
  }

  if (error.teamNeeds) {
    return (
      <Card>
        <CardContent className="py-6">
          <Alert variant="destructive">
            <AlertDescription>{error.teamNeeds}</AlertDescription>
          </Alert>
          <Button onClick={handleRefresh} className="mt-4">
            Try Again
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (!teamNeeds) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <Users className="h-12 w-12 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-600 mb-2">No team analysis available</p>
          <p className="text-sm text-gray-500 mb-4">
            Load team needs to see positional gaps and depth analysis
          </p>
          <Button onClick={handleRefresh}>Load Team Needs</Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Team Needs Overview</CardTitle>
            <CardDescription>
              Positional gaps and roster depth analysis
            </CardDescription>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={loading.teamNeeds}
          >
            Refresh
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Competitive Window */}
        <div className="p-4 rounded-lg bg-gray-50">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-gray-600" />
              <h3 className="font-semibold text-gray-900">
                Competitive Window
              </h3>
            </div>
            <Badge className={getWindowColor(teamNeeds.competitive_window)}>
              {teamNeeds.competitive_window.charAt(0).toUpperCase() +
                teamNeeds.competitive_window.slice(1)}
            </Badge>
          </div>
          <p className="text-sm text-gray-600">
            {teamNeeds.competitive_window === 'contending'
              ? 'Your team is positioned to compete now. Focus on win-now prospects and immediate contributors.'
              : teamNeeds.competitive_window === 'transitional'
                ? 'Your team is in transition. Balance between current contributors and future assets.'
                : 'Your team is rebuilding. Prioritize high-upside prospects with longer timelines.'}
          </p>
        </div>

        {/* Positional Needs */}
        <div>
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle className="h-5 w-5 text-gray-600" />
            <h3 className="font-semibold text-gray-900">Positional Needs</h3>
          </div>
          {teamNeeds.positional_needs.length === 0 ? (
            <p className="text-sm text-gray-500">
              No critical positional needs identified
            </p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {teamNeeds.positional_needs.map((need, index) => (
                <div
                  key={index}
                  className="p-3 rounded-lg border border-gray-200 hover:border-blue-300 transition-colors"
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-semibold text-gray-900">
                      {need.position}
                    </span>
                    <Badge className={getSeverityColor(need.severity)}>
                      {need.severity}
                    </Badge>
                  </div>
                  <p className="text-xs text-gray-600">
                    Timeline:{' '}
                    <span className="font-medium">
                      {need.timeline.replace('_', ' ')}
                    </span>
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Depth Chart Analysis */}
        <div>
          <div className="flex items-center gap-2 mb-3">
            <Users className="h-5 w-5 text-gray-600" />
            <h3 className="font-semibold text-gray-900">
              Depth Chart Analysis
            </h3>
          </div>
          <div className="space-y-2">
            {Object.entries(teamNeeds.depth_analysis).map(
              ([position, depth]: [string, DepthAnalysis]) => {
                const gap = getGapIndicator(depth.gap_score);
                return (
                  <div
                    key={position}
                    className="flex items-center justify-between p-3 rounded-lg bg-gray-50"
                  >
                    <div className="flex items-center gap-3">
                      <span className="font-medium text-gray-900 w-12">
                        {position}
                      </span>
                      <div className="flex items-center gap-2 text-sm text-gray-600">
                        <span>{depth.starters} starters</span>
                        <span className="text-gray-400">•</span>
                        <span>{depth.depth} depth</span>
                      </div>
                    </div>
                    <Badge className={`${gap.color} bg-transparent border-0`}>
                      {gap.label}
                    </Badge>
                  </div>
                );
              }
            )}
          </div>
        </div>

        {/* Future Needs */}
        {(teamNeeds.future_needs['2_year'].length > 0 ||
          teamNeeds.future_needs['3_year'].length > 0) && (
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Calendar className="h-5 w-5 text-gray-600" />
              <h3 className="font-semibold text-gray-900">
                Future Roster Needs
              </h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {teamNeeds.future_needs['2_year'].length > 0 && (
                <div className="p-3 rounded-lg bg-blue-50 border border-blue-200">
                  <h4 className="text-sm font-semibold text-blue-900 mb-2">
                    2-Year Outlook
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {teamNeeds.future_needs['2_year'].map((position, index) => (
                      <Badge
                        key={index}
                        variant="outline"
                        className="border-blue-300"
                      >
                        {position}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
              {teamNeeds.future_needs['3_year'].length > 0 && (
                <div className="p-3 rounded-lg bg-purple-50 border border-purple-200">
                  <h4 className="text-sm font-semibold text-purple-900 mb-2">
                    3-Year Outlook
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {teamNeeds.future_needs['3_year'].map((position, index) => (
                      <Badge
                        key={index}
                        variant="outline"
                        className="border-purple-300"
                      >
                        {position}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
