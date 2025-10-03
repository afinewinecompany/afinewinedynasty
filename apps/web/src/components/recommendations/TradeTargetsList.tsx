/**
 * Trade Targets List Component
 *
 * Displays buy-low candidates, sell-high opportunities, and value arbitrage
 * recommendations based on market inefficiencies and team context.
 *
 * @component TradeTargetsList
 * @since 1.0.0
 */

'use client';

import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, TrendingDown, TrendingUp, Repeat, Target } from 'lucide-react';
import { useRecommendations } from '@/hooks/useRecommendations';
import type { TradeTargetCandidate, TradeTargetsQuery } from '@/types/recommendations';

/**
 * Component props
 */
interface TradeTargetsListProps {
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
 * Trade targets list component
 *
 * @param props - Component props
 * @returns Rendered component
 *
 * @example
 * ```tsx
 * <TradeTargetsList
 *   leagueId="abc123"
 *   autoLoad={true}
 *   onProspectClick={(id) => router.push(`/prospects/${id}`)}
 * />
 * ```
 *
 * @since 1.0.0
 */
export function TradeTargetsList({
  leagueId,
  autoLoad = true,
  onProspectClick,
  onRefresh,
}: TradeTargetsListProps) {
  const { tradeTargets, loading, error, fetchTradeTargets } = useRecommendations();
  const [activeCategory, setActiveCategory] = useState<'all' | 'buy_low' | 'sell_high' | 'arbitrage'>('all');

  // Auto-load on mount
  useEffect(() => {
    if (autoLoad && leagueId) {
      fetchTradeTargets(leagueId);
    }
  }, [autoLoad, leagueId, fetchTradeTargets]);

  /**
   * Get opportunity type badge
   */
  const getOpportunityBadge = (type: TradeTargetCandidate['opportunity_type']) => {
    const badges = {
      buy_low: { label: 'Buy Low', color: 'bg-green-100 text-green-800', icon: TrendingDown },
      sell_high: { label: 'Sell High', color: 'bg-orange-100 text-orange-800', icon: TrendingUp },
      arbitrage: { label: 'Arbitrage', color: 'bg-purple-100 text-purple-800', icon: Repeat },
    };
    return badges[type];
  };

  /**
   * Handle refresh
   */
  const handleRefresh = () => {
    const query: TradeTargetsQuery = activeCategory !== 'all' ? { category: activeCategory } : undefined;
    fetchTradeTargets(leagueId, query);
    onRefresh?.();
  };

  /**
   * Handle category filter change
   */
  const handleCategoryChange = (category: typeof activeCategory) => {
    setActiveCategory(category);
    const query: TradeTargetsQuery = category !== 'all' ? { category } : undefined;
    fetchTradeTargets(leagueId, query);
  };

  /**
   * Render candidate card
   */
  const renderCandidate = (candidate: TradeTargetCandidate) => {
    const badge = getOpportunityBadge(candidate.opportunity_type);
    const Icon = badge.icon;

    return (
      <div
        key={candidate.prospect_id}
        onClick={() => onProspectClick?.(candidate.prospect_id)}
        className="p-4 rounded-lg border border-gray-200 hover:border-blue-300 hover:shadow-md transition-all cursor-pointer"
      >
        {/* Header */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex-1">
            <h3 className="font-semibold text-gray-900 text-lg">{candidate.name}</h3>
            <div className="flex items-center gap-2 mt-1">
              <Badge variant="outline">{candidate.position}</Badge>
            </div>
          </div>
          <Badge className={badge.color}>
            <Icon className="h-3 w-3 mr-1" />
            {badge.label}
          </Badge>
        </div>

        {/* Value Comparison */}
        <div className="grid grid-cols-2 gap-3 mb-3">
          <div className="p-2 rounded-lg bg-gray-50">
            <div className="text-xs text-gray-600 mb-1">Current Value</div>
            <div className="text-sm font-semibold text-gray-900">{candidate.current_value}</div>
          </div>
          <div className="p-2 rounded-lg bg-blue-50">
            <div className="text-xs text-blue-700 mb-1">Target Value</div>
            <div className="text-sm font-semibold text-blue-900">{candidate.target_value}</div>
          </div>
        </div>

        {/* Reasoning */}
        <div className="p-3 rounded-lg bg-gray-50">
          <p className="text-sm text-gray-700">{candidate.reasoning}</p>
        </div>
      </div>
    );
  };

  if (loading.tradeTargets) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
          <span className="ml-2 text-gray-600">Finding trade opportunities...</span>
        </CardContent>
      </Card>
    );
  }

  if (error.tradeTargets) {
    return (
      <Card>
        <CardContent className="py-6">
          <Alert variant="destructive">
            <AlertDescription>{error.tradeTargets}</AlertDescription>
          </Alert>
          <Button onClick={handleRefresh} className="mt-4">
            Try Again
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (!tradeTargets) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <Target className="h-12 w-12 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-600 mb-2">No trade targets available</p>
          <p className="text-sm text-gray-500 mb-4">
            Load trade targets to find buy-low and sell-high opportunities
          </p>
          <Button onClick={handleRefresh}>Load Trade Targets</Button>
        </CardContent>
      </Card>
    );
  }

  const hasTargets =
    tradeTargets.buy_low_candidates.length > 0 ||
    tradeTargets.sell_high_opportunities.length > 0 ||
    tradeTargets.trade_value_arbitrage.length > 0;

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Trade Targets</CardTitle>
            <CardDescription>Buy-low and sell-high opportunities for your team</CardDescription>
          </div>
          <Button variant="outline" size="sm" onClick={handleRefresh} disabled={loading.tradeTargets}>
            Refresh
          </Button>
        </div>

        {/* Category Filters */}
        <div className="flex flex-wrap gap-2 mt-4">
          <Button
            variant={activeCategory === 'all' ? 'default' : 'outline'}
            size="sm"
            onClick={() => handleCategoryChange('all')}
          >
            All
          </Button>
          <Button
            variant={activeCategory === 'buy_low' ? 'default' : 'outline'}
            size="sm"
            onClick={() => handleCategoryChange('buy_low')}
          >
            <TrendingDown className="h-4 w-4 mr-1" />
            Buy Low
          </Button>
          <Button
            variant={activeCategory === 'sell_high' ? 'default' : 'outline'}
            size="sm"
            onClick={() => handleCategoryChange('sell_high')}
          >
            <TrendingUp className="h-4 w-4 mr-1" />
            Sell High
          </Button>
          <Button
            variant={activeCategory === 'arbitrage' ? 'default' : 'outline'}
            size="sm"
            onClick={() => handleCategoryChange('arbitrage')}
          >
            <Repeat className="h-4 w-4 mr-1" />
            Arbitrage
          </Button>
        </div>
      </CardHeader>

      <CardContent>
        {!hasTargets ? (
          <div className="py-8 text-center">
            <p className="text-gray-600 mb-2">No trade targets found</p>
            <p className="text-sm text-gray-500">
              Try adjusting your filters or check back later for new opportunities
            </p>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Buy Low Candidates */}
            {(activeCategory === 'all' || activeCategory === 'buy_low') &&
              tradeTargets.buy_low_candidates.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <TrendingDown className="h-5 w-5 text-green-600" />
                    <h3 className="font-semibold text-gray-900">Buy Low Candidates</h3>
                    <Badge className="bg-green-100 text-green-800">
                      {tradeTargets.buy_low_candidates.length}
                    </Badge>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {tradeTargets.buy_low_candidates.map(renderCandidate)}
                  </div>
                </div>
              )}

            {/* Sell High Opportunities */}
            {(activeCategory === 'all' || activeCategory === 'sell_high') &&
              tradeTargets.sell_high_opportunities.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <TrendingUp className="h-5 w-5 text-orange-600" />
                    <h3 className="font-semibold text-gray-900">Sell High Opportunities</h3>
                    <Badge className="bg-orange-100 text-orange-800">
                      {tradeTargets.sell_high_opportunities.length}
                    </Badge>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {tradeTargets.sell_high_opportunities.map(renderCandidate)}
                  </div>
                </div>
              )}

            {/* Value Arbitrage */}
            {(activeCategory === 'all' || activeCategory === 'arbitrage') &&
              tradeTargets.trade_value_arbitrage.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <Repeat className="h-5 w-5 text-purple-600" />
                    <h3 className="font-semibold text-gray-900">Value Arbitrage</h3>
                    <Badge className="bg-purple-100 text-purple-800">
                      {tradeTargets.trade_value_arbitrage.length}
                    </Badge>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {tradeTargets.trade_value_arbitrage.map(renderCandidate)}
                  </div>
                </div>
              )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
