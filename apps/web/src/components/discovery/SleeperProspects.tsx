'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import LoadingSpinner from '@/components/ui/LoadingSpinner';
import ErrorMessage from '@/components/ui/ErrorMessage';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Eye, TrendingUp, AlertCircle, ExternalLink, Star } from 'lucide-react';

/**
 * Represents a sleeper prospect with undervaluation metrics
 *
 * @interface SleeperProspect
 * @since 1.0.0
 */
interface SleeperProspect {
  /** Unique prospect identifier */
  prospect_id: number;
  /** Prospect's full name */
  prospect_name: string;
  /** Primary position */
  position: string;
  /** Parent organization */
  organization: string;
  /** Current age */
  age: number;
  /** ML model confidence score (0-1) */
  ml_confidence: number;
  /** Industry consensus ranking position */
  consensus_ranking: number;
  /** ML-predicted ranking position */
  ml_ranking: number;
  /** Gap between ML and consensus rankings */
  ranking_differential: number;
  /** Composite sleeper score (0-100) */
  sleeper_score: number;
  /** ML confidence level category */
  confidence_level: 'High' | 'Medium' | 'Low';
  /** Specific factors indicating undervaluation */
  undervaluation_factors: string[];
  /** Recent performance trending data */
  recent_performance: {
    /** Type of statistical metric */
    stat_type: string;
    /** Current value of the metric */
    value: number;
    /** Performance trend direction */
    trend: 'up' | 'down' | 'stable';
  }[];
  /** Explanation of why prospect is considered a sleeper */
  discovery_reasoning: string;
}

/**
 * Props for the SleeperProspects component
 *
 * @interface SleeperProspectsProps
 * @since 1.0.0
 */
interface SleeperProspectsProps {
  /** Array of sleeper prospect candidates */
  prospects?: SleeperProspect[];
  /** Loading state indicator */
  isLoading?: boolean;
  /** Error object from failed operations */
  error?: any;
  /** Callback to refresh sleeper prospects data */
  onRefresh?: () => void;
}

/**
 * Sleeper Prospects Discovery Component
 *
 * Displays undervalued prospects identified through ML confidence scoring
 * vs consensus ranking differential analysis. Finds players where machine
 * learning models show high confidence but industry consensus rankings
 * suggest they are being overlooked or undervalued by the market.
 *
 * Features:
 * - ML confidence vs consensus ranking comparison with gap visualization
 * - Sleeper score visualization (0-100 scale) with color coding
 * - Undervaluation factor badges showing specific opportunity indicators
 * - Recent performance indicators with trend arrows
 * - Discovery reasoning explanations with detailed analysis
 * - Confidence level display showing ML prediction strength
 * - Quick links to prospect profiles
 * - Refresh capability for updated analysis
 *
 * @component
 * @param {SleeperProspectsProps} props - Component properties
 * @returns {JSX.Element} Sleeper prospects discovery interface with ML analysis
 *
 * @example
 * ```tsx
 * <SleeperProspects
 *   prospects={sleeperData}
 *   isLoading={isLoadingSleepers}
 *   error={sleeperError}
 *   onRefresh={refetchSleeperProspects}
 * />
 * ```
 *
 * @since 1.0.0
 * @version 3.4.0
 */
export function SleeperProspects({
  prospects = [],
  isLoading = false,
  error,
  onRefresh,
}: SleeperProspectsProps) {
  const [selectedProspect, setSelectedProspect] = useState<number | null>(null);
  const [sortBy, setSortBy] = useState<
    'sleeper_score' | 'differential' | 'confidence'
  >('sleeper_score');

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
          <ErrorMessage message="Failed to load sleeper prospects" />
          {onRefresh && (
            <Button onClick={onRefresh} className="mt-4">
              Try Again
            </Button>
          )}
        </CardContent>
      </Card>
    );
  }

  const sortedProspects = [...prospects].sort((a, b) => {
    switch (sortBy) {
      case 'sleeper_score':
        return b.sleeper_score - a.sleeper_score;
      case 'differential':
        return b.ranking_differential - a.ranking_differential;
      case 'confidence':
        return b.ml_confidence - a.ml_confidence;
      default:
        return 0;
    }
  });

  const getConfidenceBadgeColor = (level: string) => {
    switch (level) {
      case 'High':
        return 'bg-green-100 text-green-800';
      case 'Medium':
        return 'bg-yellow-100 text-yellow-800';
      case 'Low':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getSleeperScoreColor = (score: number) => {
    if (score >= 8) return 'text-purple-600';
    if (score >= 6) return 'text-blue-600';
    if (score >= 4) return 'text-yellow-600';
    return 'text-gray-600';
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Eye className="h-5 w-5" />
                Sleeper Prospects
              </CardTitle>
              <p className="text-sm text-gray-600 mt-1">
                Undervalued prospects with high ML confidence vs consensus
                rankings
              </p>
            </div>
            <div className="flex items-center gap-2">
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as any)}
                className="text-sm border rounded-md px-3 py-1"
              >
                <option value="sleeper_score">Sleeper Score</option>
                <option value="differential">Ranking Gap</option>
                <option value="confidence">ML Confidence</option>
              </select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {sortedProspects.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              No sleeper prospects identified with current parameters
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {sortedProspects.map((prospect) => (
                <Card
                  key={prospect.prospect_id}
                  className={`cursor-pointer transition-all hover:shadow-lg ${
                    selectedProspect === prospect.prospect_id
                      ? 'ring-2 ring-purple-500'
                      : ''
                  }`}
                  onClick={() =>
                    setSelectedProspect(
                      selectedProspect === prospect.prospect_id
                        ? null
                        : prospect.prospect_id
                    )
                  }
                >
                  <CardContent className="p-4">
                    {/* Header */}
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        <Link
                          href={`/prospects/${prospect.prospect_id}`}
                          className="font-semibold text-gray-900 hover:text-blue-600 flex items-center gap-1"
                          onClick={(e) => e.stopPropagation()}
                        >
                          {prospect.prospect_name}
                          <ExternalLink className="h-3 w-3" />
                        </Link>
                        <div className="flex items-center gap-2 mt-1">
                          <span className="text-sm text-gray-600">
                            {prospect.position} | {prospect.organization}
                          </span>
                          <span className="text-sm text-gray-500">
                            Age {prospect.age}
                          </span>
                        </div>
                      </div>
                      <div className="flex flex-col items-end gap-1">
                        <div
                          className={`text-2xl font-bold ${getSleeperScoreColor(prospect.sleeper_score)}`}
                        >
                          {prospect.sleeper_score.toFixed(1)}
                        </div>
                        <Badge
                          className={getConfidenceBadgeColor(
                            prospect.confidence_level
                          )}
                        >
                          {prospect.confidence_level}
                        </Badge>
                      </div>
                    </div>

                    {/* Rankings Comparison */}
                    <div className="grid grid-cols-3 gap-2 mb-3 p-2 bg-gray-50 rounded">
                      <div>
                        <div className="text-xs text-gray-500">ML Rank</div>
                        <div className="font-semibold">
                          {prospect.ml_ranking}
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-gray-500">Consensus</div>
                        <div className="font-semibold">
                          {prospect.consensus_ranking}
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-gray-500">Gap</div>
                        <div className="font-semibold text-purple-600">
                          +{prospect.ranking_differential}
                        </div>
                      </div>
                    </div>

                    {/* ML Confidence */}
                    <div className="mb-3">
                      <div className="flex items-center justify-between text-sm mb-1">
                        <span className="text-gray-600">ML Confidence</span>
                        <span className="font-medium">
                          {(prospect.ml_confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-purple-600 h-2 rounded-full transition-all"
                          style={{ width: `${prospect.ml_confidence * 100}%` }}
                        />
                      </div>
                    </div>

                    {/* Undervaluation Factors */}
                    {prospect.undervaluation_factors.length > 0 && (
                      <div className="mb-3">
                        <div className="text-xs text-gray-500 mb-1">
                          Why Undervalued
                        </div>
                        <div className="flex flex-wrap gap-1">
                          {prospect.undervaluation_factors.map(
                            (factor, idx) => (
                              <Badge
                                key={idx}
                                variant="outline"
                                className="text-xs"
                              >
                                {factor}
                              </Badge>
                            )
                          )}
                        </div>
                      </div>
                    )}

                    {/* Expanded Details */}
                    {selectedProspect === prospect.prospect_id && (
                      <div className="mt-3 pt-3 border-t space-y-3">
                        {/* Recent Performance */}
                        {prospect.recent_performance.length > 0 && (
                          <div>
                            <div className="text-sm font-medium mb-2">
                              Recent Performance
                            </div>
                            <div className="grid grid-cols-2 gap-2">
                              {prospect.recent_performance.map((stat, idx) => (
                                <div
                                  key={idx}
                                  className="flex items-center justify-between text-sm"
                                >
                                  <span className="text-gray-600">
                                    {stat.stat_type}
                                  </span>
                                  <span className="flex items-center gap-1">
                                    <span className="font-medium">
                                      {stat.value.toFixed(3)}
                                    </span>
                                    {stat.trend === 'up' && (
                                      <TrendingUp className="h-3 w-3 text-green-500" />
                                    )}
                                    {stat.trend === 'down' && (
                                      <TrendingUp className="h-3 w-3 text-red-500 rotate-180" />
                                    )}
                                  </span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Discovery Reasoning */}
                        <div>
                          <div className="text-sm font-medium mb-1 flex items-center gap-1">
                            <AlertCircle className="h-4 w-4" />
                            Discovery Insight
                          </div>
                          <p className="text-sm text-gray-600">
                            {prospect.discovery_reasoning}
                          </p>
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Summary Stats */}
      {prospects.length > 0 && (
        <Card>
          <CardContent className="py-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <div className="text-sm text-gray-500">Total Sleepers</div>
                <div className="text-2xl font-bold">{prospects.length}</div>
              </div>
              <div>
                <div className="text-sm text-gray-500">Avg Sleeper Score</div>
                <div className="text-2xl font-bold">
                  {(
                    prospects.reduce((sum, p) => sum + p.sleeper_score, 0) /
                    prospects.length
                  ).toFixed(1)}
                </div>
              </div>
              <div>
                <div className="text-sm text-gray-500">Max Ranking Gap</div>
                <div className="text-2xl font-bold">
                  +{Math.max(...prospects.map((p) => p.ranking_differential))}
                </div>
              </div>
              <div>
                <div className="text-sm text-gray-500">High Confidence</div>
                <div className="text-2xl font-bold">
                  {
                    prospects.filter((p) => p.confidence_level === 'High')
                      .length
                  }
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
