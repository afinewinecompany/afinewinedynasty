/**
 * Stash Candidates Component
 *
 * Displays roster spot availability and high-upside stash candidates
 * optimized for rebuild-focused teams and long-term value.
 *
 * @component StashCandidates
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
import { Loader2, Package, TrendingUp, Calendar, Sparkles } from 'lucide-react';
import { useRecommendations } from '@/hooks/useRecommendations';
import type { StashCandidate } from '@/types/recommendations';

/**
 * Component props
 */
interface StashCandidatesProps {
  /** Fantrax league ID */
  leagueId: string;
  /** Whether to auto-load data on mount */
  autoLoad?: boolean;
  /** Optional callback when prospect is clicked */
  onProspectClick?: (prospectId: number) => void;
  /** Optional callback when refresh is triggered */
  onRefresh?: () => void;
}

/**
 * Stash candidates component
 *
 * @param props - Component props
 * @returns Rendered component
 *
 * @example
 * ```tsx
 * <StashCandidates
 *   leagueId="abc123"
 *   autoLoad={true}
 *   onProspectClick={(id) => router.push(`/prospects/${id}`)}
 * />
 * ```
 *
 * @since 1.0.0
 */
export function StashCandidates({
  leagueId,
  autoLoad = true,
  onProspectClick,
  onRefresh,
}: StashCandidatesProps) {
  const { stashCandidates, loading, error, fetchStashCandidates } =
    useRecommendations();

  // Auto-load on mount
  useEffect(() => {
    if (autoLoad && leagueId) {
      fetchStashCandidates(leagueId);
    }
  }, [autoLoad, leagueId, fetchStashCandidates]);

  /**
   * Get upside score color
   */
  const getUpsideColor = (score: number): string => {
    if (score >= 80) return 'bg-purple-50 text-purple-700 border-purple-200';
    if (score >= 60) return 'bg-blue-50 text-blue-700 border-blue-200';
    if (score >= 40) return 'bg-green-50 text-green-700 border-green-200';
    return 'bg-gray-50 text-gray-700 border-gray-200';
  };

  /**
   * Get upside label
   */
  const getUpsideLabel = (score: number): string => {
    if (score >= 80) return 'Elite Upside';
    if (score >= 60) return 'High Upside';
    if (score >= 40) return 'Moderate Upside';
    return 'Speculative';
  };

  /**
   * Handle refresh
   */
  const handleRefresh = () => {
    fetchStashCandidates(leagueId);
    onRefresh?.();
  };

  /**
   * Render stash candidate card
   */
  const renderCandidate = (candidate: StashCandidate) => {
    const upsideColor = getUpsideColor(candidate.upside_score);
    const upsideLabel = getUpsideLabel(candidate.upside_score);

    return (
      <div
        key={candidate.prospect_id}
        onClick={() => onProspectClick?.(candidate.prospect_id)}
        className="p-4 rounded-lg border border-gray-200 hover:border-blue-300 hover:shadow-md transition-all cursor-pointer"
      >
        {/* Header */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex-1">
            <h3 className="font-semibold text-gray-900 text-lg">
              {candidate.name}
            </h3>
            <div className="flex items-center gap-2 mt-1">
              <Badge variant="outline">{candidate.position}</Badge>
              <div className="flex items-center gap-1 text-xs text-gray-500">
                <Calendar className="h-3 w-3" />
                <span>ETA: {candidate.eta}</span>
              </div>
            </div>
          </div>

          {/* Upside Score */}
          <div
            className={`px-3 py-2 rounded-lg border text-center ${upsideColor}`}
          >
            <div className="text-xl font-bold">
              {candidate.upside_score.toFixed(0)}
            </div>
            <div className="text-xs">Upside</div>
          </div>
        </div>

        {/* Upside Badge */}
        <div className="mb-3">
          <Badge
            className={upsideColor
              .replace('bg-', 'bg-')
              .replace('text-', 'text-')}
          >
            <Sparkles className="h-3 w-3 mr-1" />
            {upsideLabel}
          </Badge>
        </div>

        {/* Reasoning */}
        <div className="p-3 rounded-lg bg-gray-50">
          <p className="text-sm text-gray-700">{candidate.reasoning}</p>
        </div>
      </div>
    );
  };

  if (loading.stashCandidates) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
          <span className="ml-2 text-gray-600">
            Finding stash candidates...
          </span>
        </CardContent>
      </Card>
    );
  }

  if (error.stashCandidates) {
    return (
      <Card>
        <CardContent className="py-6">
          <Alert variant="destructive">
            <AlertDescription>{error.stashCandidates}</AlertDescription>
          </Alert>
          <Button onClick={handleRefresh} className="mt-4">
            Try Again
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (!stashCandidates) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <Package className="h-12 w-12 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-600 mb-2">No stash candidates available</p>
          <p className="text-sm text-gray-500 mb-4">
            Load stash candidates to find high-upside prospects for your roster
          </p>
          <Button onClick={handleRefresh}>Load Stash Candidates</Button>
        </CardContent>
      </Card>
    );
  }

  const hasSpots = stashCandidates.available_spots > 0;
  const hasCandidates = stashCandidates.stash_candidates.length > 0;

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Stash Candidates</CardTitle>
            <CardDescription>
              High-upside prospects to stash on your roster
            </CardDescription>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={loading.stashCandidates}
          >
            Refresh
          </Button>
        </div>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Roster Spots Indicator */}
        <div className="p-4 rounded-lg bg-blue-50 border border-blue-200">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Package className="h-5 w-5 text-blue-600" />
              <div>
                <h3 className="font-semibold text-blue-900">
                  Available Roster Spots
                </h3>
                <p className="text-sm text-blue-700">
                  {hasSpots
                    ? `You have ${stashCandidates.available_spots} spot${
                        stashCandidates.available_spots > 1 ? 's' : ''
                      } available for stashing prospects`
                    : 'Your roster is currently full'}
                </p>
              </div>
            </div>
            <div className="text-3xl font-bold text-blue-600">
              {stashCandidates.available_spots}
            </div>
          </div>
        </div>

        {/* Opportunity Cost Notice */}
        {hasSpots && hasCandidates && (
          <Alert>
            <AlertDescription className="flex items-start gap-2">
              <TrendingUp className="h-4 w-4 text-blue-600 mt-0.5 flex-shrink-0" />
              <div>
                <span className="font-medium">Maximize your upside:</span> These
                high-potential prospects can provide significant long-term
                value. Consider your team's competitive window when making stash
                decisions.
              </div>
            </AlertDescription>
          </Alert>
        )}

        {/* Stash Candidates List */}
        {!hasCandidates ? (
          <div className="py-8 text-center">
            <p className="text-gray-600 mb-2">No stash candidates found</p>
            <p className="text-sm text-gray-500">
              {hasSpots
                ? 'Check back later for new high-upside prospects to stash'
                : 'Free up roster spots to receive stash recommendations'}
            </p>
          </div>
        ) : (
          <div>
            <div className="flex items-center gap-2 mb-4">
              <Sparkles className="h-5 w-5 text-purple-600" />
              <h3 className="font-semibold text-gray-900">
                Recommended Stash Targets
              </h3>
              <Badge className="bg-purple-100 text-purple-800">
                {stashCandidates.stash_candidates.length}
              </Badge>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {stashCandidates.stash_candidates.map(renderCandidate)}
            </div>
          </div>
        )}

        {/* Info Footer */}
        {!hasSpots && (
          <div className="p-4 rounded-lg bg-yellow-50 border border-yellow-200">
            <p className="text-sm text-yellow-800">
              <span className="font-medium">Roster Management Tip:</span>{' '}
              Consider dropping underperforming veterans or low-upside depth
              pieces to make room for these stash candidates with higher
              long-term potential.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
