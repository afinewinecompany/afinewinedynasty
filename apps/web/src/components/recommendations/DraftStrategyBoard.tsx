/**
 * Draft Strategy Board Component
 *
 * Displays tiered draft recommendations with BPA vs Need guidance,
 * sleeper candidates, and pick-specific contextual recommendations.
 *
 * @component DraftStrategyBoard
 * @since 1.0.0
 */

'use client';

import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Input } from '@/components/ui/input';
import { Loader2, Trophy, Star, Zap, Target } from 'lucide-react';
import { useRecommendations } from '@/hooks/useRecommendations';
import type { DraftProspectRecommendation } from '@/types/recommendations';

/**
 * Component props
 */
interface DraftStrategyBoardProps {
  /** Fantrax league ID */
  leagueId: string;
  /** Whether to auto-load data on mount */
  autoLoad?: boolean;
  /** Optional initial pick number */
  initialPickNumber?: number;
  /** Optional callback when prospect is clicked */
  onProspectClick?: (prospectId: number) => void;
  /** Optional callback when refresh is triggered */
  onRefresh?: () => void;
}

/**
 * Draft strategy board component
 *
 * @param props - Component props
 * @returns Rendered component
 *
 * @example
 * ```tsx
 * <DraftStrategyBoard
 *   leagueId="abc123"
 *   autoLoad={true}
 *   initialPickNumber={5}
 *   onProspectClick={(id) => router.push(`/prospects/${id}`)}
 * />
 * ```
 *
 * @since 1.0.0
 */
export function DraftStrategyBoard({
  leagueId,
  autoLoad = true,
  initialPickNumber,
  onProspectClick,
  onRefresh,
}: DraftStrategyBoardProps) {
  const { draftStrategy, loading, error, fetchDraftStrategy } = useRecommendations();
  const [pickNumber, setPickNumber] = useState<number | undefined>(initialPickNumber);
  const [inputValue, setInputValue] = useState<string>(initialPickNumber?.toString() || '');

  // Auto-load on mount
  useEffect(() => {
    if (autoLoad && leagueId) {
      fetchDraftStrategy(leagueId, pickNumber ? { pick_number: pickNumber } : undefined);
    }
  }, [autoLoad, leagueId]); // Only run on mount

  /**
   * Get tier badge color
   */
  const getTierBadge = (tier: number) => {
    const badges = [
      { label: 'Tier 1', color: 'bg-purple-100 text-purple-800', icon: Trophy },
      { label: 'Tier 2', color: 'bg-blue-100 text-blue-800', icon: Star },
      { label: 'Tier 3', color: 'bg-green-100 text-green-800', icon: Target },
    ];
    return badges[tier - 1] || badges[2];
  };

  /**
   * Get need match color
   */
  const getNeedMatchColor = (needMatch: number): string => {
    if (needMatch >= 80) return 'text-green-600';
    if (needMatch >= 60) return 'text-blue-600';
    if (needMatch >= 40) return 'text-yellow-600';
    return 'text-gray-600';
  };

  /**
   * Handle pick number update
   */
  const handlePickNumberUpdate = () => {
    const pick = inputValue ? parseInt(inputValue, 10) : undefined;
    if (pick && pick > 0) {
      setPickNumber(pick);
      fetchDraftStrategy(leagueId, { pick_number: pick });
    } else {
      setPickNumber(undefined);
      fetchDraftStrategy(leagueId);
    }
  };

  /**
   * Handle refresh
   */
  const handleRefresh = () => {
    fetchDraftStrategy(leagueId, pickNumber ? { pick_number: pickNumber } : undefined);
    onRefresh?.();
  };

  /**
   * Render prospect recommendation
   */
  const renderProspect = (prospect: DraftProspectRecommendation) => (
    <div
      key={prospect.prospect_id}
      onClick={() => onProspectClick?.(prospect.prospect_id)}
      className="p-3 rounded-lg border border-gray-200 hover:border-blue-300 hover:shadow-md transition-all cursor-pointer"
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex-1">
          <h4 className="font-semibold text-gray-900">{prospect.name}</h4>
          <div className="flex items-center gap-2 mt-1">
            <Badge variant="outline">{prospect.position}</Badge>
            <Badge className="bg-gray-100 text-gray-800">{prospect.draft_value}</Badge>
          </div>
        </div>
        <div className={`text-right ${getNeedMatchColor(prospect.need_match)}`}>
          <div className="text-lg font-bold">{prospect.need_match.toFixed(0)}%</div>
          <div className="text-xs">Need Match</div>
        </div>
      </div>
    </div>
  );

  if (loading.draftStrategy) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
          <span className="ml-2 text-gray-600">Generating draft strategy...</span>
        </CardContent>
      </Card>
    );
  }

  if (error.draftStrategy) {
    return (
      <Card>
        <CardContent className="py-6">
          <Alert variant="destructive">
            <AlertDescription>{error.draftStrategy}</AlertDescription>
          </Alert>
          <Button onClick={handleRefresh} className="mt-4">
            Try Again
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (!draftStrategy) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <Trophy className="h-12 w-12 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-600 mb-2">No draft strategy available</p>
          <p className="text-sm text-gray-500 mb-4">
            Load draft strategy to see tiered recommendations
          </p>
          <Button onClick={handleRefresh}>Load Draft Strategy</Button>
        </CardContent>
      </Card>
    );
  }

  const tier1Badge = getTierBadge(1);
  const tier2Badge = getTierBadge(2);
  const tier3Badge = getTierBadge(3);

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Draft Strategy Board</CardTitle>
            <CardDescription>Tiered prospects and draft recommendations</CardDescription>
          </div>
          <Button variant="outline" size="sm" onClick={handleRefresh} disabled={loading.draftStrategy}>
            Refresh
          </Button>
        </div>

        {/* Pick Number Input */}
        <div className="flex items-center gap-2 mt-4">
          <Input
            type="number"
            placeholder="Enter pick number..."
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                handlePickNumberUpdate();
              }
            }}
            className="max-w-xs"
            min="1"
          />
          <Button size="sm" onClick={handlePickNumberUpdate}>
            Update
          </Button>
        </div>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* BPA vs Need Recommendation */}
        <div className="p-4 rounded-lg bg-blue-50 border border-blue-200">
          <div className="flex items-center gap-2 mb-2">
            <Target className="h-5 w-5 text-blue-600" />
            <h3 className="font-semibold text-blue-900">Draft Guidance</h3>
          </div>
          <p className="text-sm text-blue-700">{draftStrategy.bpa_vs_need}</p>
        </div>

        {/* Tier 1 */}
        {draftStrategy.tier_1.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Trophy className="h-5 w-5 text-purple-600" />
              <h3 className="font-semibold text-gray-900">{tier1Badge.label}</h3>
              <Badge className={tier1Badge.color}>{draftStrategy.tier_1.length}</Badge>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {draftStrategy.tier_1.map(renderProspect)}
            </div>
          </div>
        )}

        {/* Tier 2 */}
        {draftStrategy.tier_2.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Star className="h-5 w-5 text-blue-600" />
              <h3 className="font-semibold text-gray-900">{tier2Badge.label}</h3>
              <Badge className={tier2Badge.color}>{draftStrategy.tier_2.length}</Badge>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {draftStrategy.tier_2.map(renderProspect)}
            </div>
          </div>
        )}

        {/* Tier 3 */}
        {draftStrategy.tier_3 && draftStrategy.tier_3.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Target className="h-5 w-5 text-green-600" />
              <h3 className="font-semibold text-gray-900">{tier3Badge.label}</h3>
              <Badge className={tier3Badge.color}>{draftStrategy.tier_3.length}</Badge>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {draftStrategy.tier_3.map(renderProspect)}
            </div>
          </div>
        )}

        {/* Sleepers */}
        {draftStrategy.sleepers.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Zap className="h-5 w-5 text-orange-600" />
              <h3 className="font-semibold text-gray-900">Sleeper Candidates</h3>
              <Badge className="bg-orange-100 text-orange-800">{draftStrategy.sleepers.length}</Badge>
            </div>
            <div className="p-4 rounded-lg bg-orange-50 border border-orange-200">
              <p className="text-sm text-orange-700 mb-3">
                High-upside prospects for late rounds with breakout potential
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {draftStrategy.sleepers.map(renderProspect)}
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
