'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import LoadingSpinner from '@/components/ui/LoadingSpinner';
import ErrorMessage from '@/components/ui/ErrorMessage';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Target, TrendingUp, TrendingDown, AlertTriangle, Info } from 'lucide-react';

interface PositionScarcityData {
  position: string;
  total_prospects: number;
  elite_prospects: number;
  avg_dynasty_value: number;
  scarcity_score: number;
  supply_demand_ratio: number;
  market_trend: 'increasing' | 'stable' | 'decreasing';
  projected_eta_distribution: {
    [year: string]: number;
  };
  top_prospects: {
    id: number;
    name: string;
    organization: string;
    grade: number;
  }[];
  dynasty_context: {
    avg_roster_need: number;
    replacement_difficulty: 'Easy' | 'Moderate' | 'Hard';
    position_premium: number;
  };
}

interface PositionScarcityProps {
  scarcityData?: PositionScarcityData[];
  isLoading?: boolean;
  error?: any;
  onRefresh?: () => void;
}

/**
 * Position Scarcity Analysis Component
 *
 * Analyzes positional supply/demand dynamics for dynasty leagues with
 * scarcity scoring and market trends. Helps identify positions with
 * limited elite prospect availability and optimal timing for acquisitions
 * based on dynasty league roster construction needs.
 *
 * Features:
 * - Position scarcity scoring (0-100 scale) with color coding
 * - Supply/demand ratio analysis for market evaluation
 * - Dynasty league context with roster need projections
 * - Market trend indicators (increasing/stable/decreasing)
 * - ETA distribution by position for timing analysis
 * - Elite prospect counts and average dynasty values
 * - Replacement difficulty assessment
 * - Position premium calculations
 * - Top prospects by position with grades
 *
 * @component
 * @param {PositionScarcityProps} props - Component properties
 * @returns {JSX.Element} Position scarcity analysis interface with dynasty context
 *
 * @example
 * ```tsx
 * <PositionScarcity
 *   scarcityData={scarcityAnalysis}
 *   isLoading={isLoadingScarcity}
 *   error={scarcityError}
 *   onRefresh={refetchScarcityData}
 * />
 * ```
 *
 * @since 1.0.0
 * @version 3.4.0
 */
export function PositionScarcity({
  scarcityData = [],
  isLoading = false,
  error,
  onRefresh
}: PositionScarcityProps) {
  const [selectedPosition, setSelectedPosition] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'scarcity' | 'value'>('scarcity');

  if (isLoading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <LoadingSpinner />
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent>
          <ErrorMessage message="Failed to load position scarcity data" />
          {onRefresh && (
            <Button onClick={onRefresh} className="mt-4">
              Try Again
            </Button>
          )}
        </CardContent>
      </Card>
    );
  }

  const sortedData = [...scarcityData].sort((a, b) => {
    if (viewMode === 'scarcity') {
      return b.scarcity_score - a.scarcity_score;
    } else {
      return b.avg_dynasty_value - a.avg_dynasty_value;
    }
  });

  const getScarcityColor = (score: number) => {
    if (score >= 80) return 'text-red-600';
    if (score >= 60) return 'text-orange-600';
    if (score >= 40) return 'text-yellow-600';
    return 'text-green-600';
  };

  const getScarcityBadge = (score: number) => {
    if (score >= 80) return { color: 'bg-red-100 text-red-800', label: 'Critical' };
    if (score >= 60) return { color: 'bg-orange-100 text-orange-800', label: 'High' };
    if (score >= 40) return { color: 'bg-yellow-100 text-yellow-800', label: 'Moderate' };
    return { color: 'bg-green-100 text-green-800', label: 'Low' };
  };

  const getDifficultyColor = (difficulty: string) => {
    switch (difficulty) {
      case 'Hard':
        return 'text-red-600';
      case 'Moderate':
        return 'text-yellow-600';
      case 'Easy':
        return 'text-green-600';
      default:
        return 'text-gray-600';
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Target className="h-5 w-5" />
                Position Scarcity Analysis
              </CardTitle>
              <p className="text-sm text-gray-600 mt-1">
                Dynasty league positional supply/demand dynamics
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant={viewMode === 'scarcity' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setViewMode('scarcity')}
              >
                Scarcity View
              </Button>
              <Button
                variant={viewMode === 'value' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setViewMode('value')}
              >
                Value View
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {sortedData.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              No position scarcity data available
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
              {sortedData.map((position) => {
                const scarcityBadge = getScarcityBadge(position.scarcity_score);
                const isSelected = selectedPosition === position.position;

                return (
                  <Card
                    key={position.position}
                    className={`cursor-pointer transition-all hover:shadow-lg ${
                      isSelected ? 'ring-2 ring-blue-500' : ''
                    }`}
                    onClick={() => setSelectedPosition(
                      isSelected ? null : position.position
                    )}
                  >
                    <CardContent className="p-4">
                      {/* Header */}
                      <div className="flex items-start justify-between mb-3">
                        <div>
                          <h3 className="text-lg font-semibold">{position.position}</h3>
                          <div className="flex items-center gap-2 mt-1">
                            <Badge className={scarcityBadge.color}>
                              {scarcityBadge.label} Scarcity
                            </Badge>
                            {position.market_trend === 'increasing' && (
                              <TrendingUp className="h-4 w-4 text-green-500" />
                            )}
                            {position.market_trend === 'decreasing' && (
                              <TrendingDown className="h-4 w-4 text-red-500" />
                            )}
                          </div>
                        </div>
                        <div className="text-right">
                          <div className={`text-2xl font-bold ${getScarcityColor(position.scarcity_score)}`}>
                            {position.scarcity_score}
                          </div>
                          <div className="text-xs text-gray-500">Scarcity</div>
                        </div>
                      </div>

                      {/* Key Metrics */}
                      <div className="grid grid-cols-2 gap-2 mb-3">
                        <div className="p-2 bg-gray-50 rounded">
                          <div className="text-xs text-gray-500">Total Prospects</div>
                          <div className="font-semibold">{position.total_prospects}</div>
                        </div>
                        <div className="p-2 bg-gray-50 rounded">
                          <div className="text-xs text-gray-500">Elite Prospects</div>
                          <div className="font-semibold">{position.elite_prospects}</div>
                        </div>
                        <div className="p-2 bg-gray-50 rounded">
                          <div className="text-xs text-gray-500">Dynasty Value</div>
                          <div className="font-semibold">{position.avg_dynasty_value.toFixed(1)}</div>
                        </div>
                        <div className="p-2 bg-gray-50 rounded">
                          <div className="text-xs text-gray-500">Supply/Demand</div>
                          <div className="font-semibold">{position.supply_demand_ratio.toFixed(2)}</div>
                        </div>
                      </div>

                      {/* Dynasty Context */}
                      <div className="flex items-center justify-between text-sm mb-3">
                        <span className="text-gray-600">Replacement Difficulty</span>
                        <span className={`font-medium ${getDifficultyColor(position.dynasty_context.replacement_difficulty)}`}>
                          {position.dynasty_context.replacement_difficulty}
                        </span>
                      </div>

                      {/* Position Premium Bar */}
                      <div className="mb-3">
                        <div className="flex items-center justify-between text-sm mb-1">
                          <span className="text-gray-600">Position Premium</span>
                          <span className="font-medium">{(position.dynasty_context.position_premium * 100).toFixed(0)}%</span>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-2">
                          <div
                            className="bg-blue-600 h-2 rounded-full transition-all"
                            style={{ width: `${position.dynasty_context.position_premium * 100}%` }}
                          />
                        </div>
                      </div>

                      {/* Expanded Details */}
                      {isSelected && (
                        <div className="mt-3 pt-3 border-t space-y-3">
                          {/* ETA Distribution */}
                          <div>
                            <div className="text-sm font-medium mb-2">Projected Supply Timeline</div>
                            <div className="flex items-end gap-1 h-16">
                              {Object.entries(position.projected_eta_distribution).slice(0, 4).map(([year, count]) => {
                                const maxCount = Math.max(...Object.values(position.projected_eta_distribution));
                                const height = (count / maxCount) * 100;
                                return (
                                  <div
                                    key={year}
                                    className="flex-1 flex flex-col items-center"
                                  >
                                    <div
                                      className="w-full bg-indigo-500 rounded-t text-xs text-white flex items-end justify-center pb-1"
                                      style={{ height: `${height}%` }}
                                    >
                                      {count}
                                    </div>
                                    <div className="text-xs mt-1">{year}</div>
                                  </div>
                                );
                              })}
                            </div>
                          </div>

                          {/* Top Prospects */}
                          <div>
                            <div className="text-sm font-medium mb-2">Top Available Prospects</div>
                            <div className="space-y-1">
                              {position.top_prospects.slice(0, 3).map((prospect) => (
                                <div
                                  key={prospect.id}
                                  className="flex items-center justify-between text-sm p-1 hover:bg-gray-50 rounded"
                                >
                                  <span>{prospect.name}</span>
                                  <div className="flex items-center gap-2">
                                    <span className="text-gray-500 text-xs">{prospect.organization}</span>
                                    <Badge variant="outline" className="text-xs">
                                      {prospect.grade}
                                    </Badge>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>

                          {/* Dynasty Insights */}
                          <div className="p-2 bg-blue-50 rounded">
                            <div className="flex items-start gap-2">
                              <Info className="h-4 w-4 text-blue-600 mt-0.5" />
                              <div className="text-xs text-blue-900">
                                <div className="font-medium mb-1">Dynasty Insight</div>
                                <div>
                                  Average roster need: {position.dynasty_context.avg_roster_need.toFixed(1)} players.
                                  {position.scarcity_score >= 60 && (
                                    <span> Consider prioritizing {position.position} prospects in upcoming drafts.</span>
                                  )}
                                  {position.market_trend === 'increasing' && (
                                    <span> Demand trending up - secure talent early.</span>
                                  )}
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Market Overview */}
      {scarcityData.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <AlertTriangle className="h-5 w-5" />
              Market Overview
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <div className="text-sm text-gray-500">Most Scarce</div>
                <div className="text-xl font-bold">
                  {sortedData[0]?.position || 'N/A'}
                </div>
              </div>
              <div>
                <div className="text-sm text-gray-500">Most Available</div>
                <div className="text-xl font-bold">
                  {sortedData[sortedData.length - 1]?.position || 'N/A'}
                </div>
              </div>
              <div>
                <div className="text-sm text-gray-500">Total Elite Prospects</div>
                <div className="text-xl font-bold">
                  {scarcityData.reduce((sum, p) => sum + p.elite_prospects, 0)}
                </div>
              </div>
              <div>
                <div className="text-sm text-gray-500">Positions Trending Up</div>
                <div className="text-xl font-bold">
                  {scarcityData.filter(p => p.market_trend === 'increasing').length}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}