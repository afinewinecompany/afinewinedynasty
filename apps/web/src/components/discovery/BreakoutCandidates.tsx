'use client';

import Link from 'next/link';
import { BreakoutCandidate } from '@/hooks/useDiscovery';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import {
  TrendingUp,
  ExternalLink,
  BarChart3,
  Target,
  Calendar,
  Zap,
  AlertCircle,
  RefreshCcw
} from 'lucide-react';

/**
 * Props for the BreakoutCandidates component
 *
 * @interface BreakoutCandidatesProps
 * @since 1.0.0
 */
interface BreakoutCandidatesProps {
  /** Array of breakout candidate prospects with performance metrics */
  candidates: BreakoutCandidate[] | undefined;
  /** Loading state indicator for data fetch */
  isLoading: boolean;
  /** Error object from failed data operations */
  error: any;
  /** Callback to refresh breakout candidates data */
  onRefresh: () => void;
}

/**
 * Breakout Candidates Component
 *
 * Displays prospects with significant recent performance improvements identified
 * through time-series analysis and statistical trending. Uses the breakout detection
 * algorithm to find players whose performance has measurably improved in the last
 * 30-60 days compared to their baseline performance.
 *
 * Features:
 * - Breakout score visualization (0-100 scale) with color coding
 * - Performance improvement metrics showing percentage gains
 * - Trend consistency indicators based on statistical significance
 * - Statistical significance display with confidence levels
 * - Comparative baseline vs recent stats with period labels
 * - Quick links to prospect profiles for deeper analysis
 * - Refresh capability for real-time updates
 * - Empty state and error handling
 *
 * @component
 * @param {BreakoutCandidatesProps} props - Component properties
 * @returns {JSX.Element} Breakout candidates discovery interface with trending metrics
 *
 * @example
 * ```tsx
 * <BreakoutCandidates
 *   candidates={breakoutData}
 *   isLoading={isLoadingBreakouts}
 *   error={breakoutError}
 *   onRefresh={refetchBreakoutCandidates}
 * />
 * ```
 *
 * @since 1.0.0
 * @version 3.4.0
 */
export function BreakoutCandidates({
  candidates,
  isLoading,
  error,
  onRefresh
}: BreakoutCandidatesProps) {
  const getBreakoutScoreColor = (score: number) => {
    if (score >= 80) return 'bg-green-500';
    if (score >= 60) return 'bg-blue-500';
    if (score >= 40) return 'bg-yellow-500';
    return 'bg-gray-400';
  };

  const getBreakoutScoreBadge = (score: number) => {
    if (score >= 80) return { variant: 'default' as const, color: 'bg-green-500', label: 'Elite Breakout' };
    if (score >= 60) return { variant: 'secondary' as const, color: 'bg-blue-500', label: 'Strong Breakout' };
    if (score >= 40) return { variant: 'outline' as const, color: 'bg-yellow-500', label: 'Emerging' };
    return { variant: 'outline' as const, color: 'bg-gray-400', label: 'Developing' };
  };

  const formatPercentage = (value: number) => {
    return `${(value * 100).toFixed(1)}%`;
  };

  const formatStat = (value: number | null | undefined, decimals = 3) => {
    if (value === null || value === undefined) return 'N/A';
    return value.toFixed(decimals);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Analyzing breakout candidates...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-900 mb-2">Analysis Failed</h3>
        <p className="text-gray-600 mb-4">
          Unable to load breakout candidate analysis. Please try again.
        </p>
        <Button variant="outline" onClick={onRefresh}>
          <RefreshCcw className="h-4 w-4 mr-2" />
          Retry Analysis
        </Button>
      </div>
    );
  }

  if (!candidates || candidates.length === 0) {
    return (
      <div className="text-center py-12">
        <TrendingUp className="h-12 w-12 text-gray-300 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-900 mb-2">No Breakout Candidates Found</h3>
        <p className="text-gray-600 mb-4">
          No prospects currently show significant performance improvements.
        </p>
        <div className="text-sm text-gray-500">
          <p>This could be due to:</p>
          <ul className="list-disc list-inside mt-2 space-y-1">
            <li>Strict improvement thresholds</li>
            <li>Limited recent statistical data</li>
            <li>Short lookback period</li>
            <li>Seasonal performance variations</li>
          </ul>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <TrendingUp className="h-6 w-6 text-green-500" />
            Breakout Candidates
          </h2>
          <p className="text-gray-600 mt-1">
            Prospects showing significant recent performance improvements
          </p>
        </div>
        <Badge variant="secondary" className="text-sm">
          {candidates.length} candidate{candidates.length !== 1 ? 's' : ''}
        </Badge>
      </div>

      {/* Candidates Grid */}
      <div className="grid gap-6">
        {candidates.map((candidate) => {
          const scoreBadge = getBreakoutScoreBadge(candidate.breakout_score);
          const isHitter = !['SP', 'RP'].includes(candidate.position);

          return (
            <Card key={candidate.prospect_id} className="hover:shadow-lg transition-shadow">
              <CardHeader className="pb-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <Link
                        href={`/prospects/${candidate.prospect_id}`}
                        className="font-bold text-xl text-gray-900 hover:text-blue-600 transition-colors"
                      >
                        {candidate.name}
                      </Link>
                      <Badge variant="outline">{candidate.position}</Badge>
                      {candidate.age && (
                        <Badge variant="secondary" className="text-xs">
                          Age {candidate.age}
                        </Badge>
                      )}
                    </div>
                    <div className="flex items-center gap-4 text-sm text-gray-600">
                      <span>{candidate.organization}</span>
                      <span>{candidate.level}</span>
                      {candidate.eta_year && (
                        <span>ETA: {candidate.eta_year}</span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="text-right">
                      <div className="flex items-center gap-2 mb-1">
                        <Zap className="h-4 w-4 text-orange-500" />
                        <span className="text-sm font-medium">Breakout Score</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Progress
                          value={candidate.breakout_score}
                          className="w-20 h-2"
                        />
                        <span className="text-lg font-bold text-gray-900">
                          {candidate.breakout_score.toFixed(0)}
                        </span>
                      </div>
                      <Badge variant={scoreBadge.variant} className="text-xs mt-1">
                        {scoreBadge.label}
                      </Badge>
                    </div>
                    <Link href={`/prospects/${candidate.prospect_id}`}>
                      <Button variant="outline" size="sm">
                        <ExternalLink className="h-4 w-4" />
                      </Button>
                    </Link>
                  </div>
                </div>
              </CardHeader>

              <CardContent className="space-y-4">
                {/* Performance Trends */}
                <div>
                  <h4 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
                    <BarChart3 className="h-4 w-4" />
                    Performance Trends
                  </h4>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="text-center">
                      <div className="text-lg font-bold text-green-600">
                        {formatPercentage(candidate.trend_indicators.max_improvement_rate)}
                      </div>
                      <div className="text-xs text-gray-500">Max Improvement</div>
                    </div>
                    <div className="text-center">
                      <div className="text-lg font-bold text-blue-600">
                        {formatPercentage(candidate.trend_indicators.avg_improvement_rate)}
                      </div>
                      <div className="text-xs text-gray-500">Avg Improvement</div>
                    </div>
                    <div className="text-center">
                      <div className="text-lg font-bold text-purple-600">
                        {formatPercentage(candidate.trend_indicators.trend_consistency)}
                      </div>
                      <div className="text-xs text-gray-500">Consistency</div>
                    </div>
                    <div className="text-center">
                      <div className="text-lg font-bold text-orange-600">
                        {formatPercentage(candidate.statistical_significance.confidence_level)}
                      </div>
                      <div className="text-xs text-gray-500">Confidence</div>
                    </div>
                  </div>
                </div>

                {/* Performance Comparison */}
                <div>
                  <h4 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
                    <Target className="h-4 w-4" />
                    Performance Comparison
                  </h4>
                  <div className="grid grid-cols-2 gap-4">
                    {/* Baseline Stats */}
                    <div className="bg-gray-50 rounded-lg p-3">
                      <div className="text-xs font-medium text-gray-600 mb-2">Baseline Period</div>
                      {isHitter ? (
                        <div className="space-y-1 text-sm">
                          <div className="flex justify-between">
                            <span>AVG:</span>
                            <span>{formatStat(candidate.baseline_stats_summary.avg_batting_avg)}</span>
                          </div>
                          <div className="flex justify-between">
                            <span>OBP:</span>
                            <span>{formatStat(candidate.baseline_stats_summary.avg_obp)}</span>
                          </div>
                          <div className="flex justify-between">
                            <span>SLG:</span>
                            <span>{formatStat(candidate.baseline_stats_summary.avg_slugging)}</span>
                          </div>
                        </div>
                      ) : (
                        <div className="space-y-1 text-sm">
                          <div className="flex justify-between">
                            <span>ERA:</span>
                            <span>{formatStat(candidate.baseline_stats_summary.avg_era, 2)}</span>
                          </div>
                          <div className="flex justify-between">
                            <span>WHIP:</span>
                            <span>{formatStat(candidate.baseline_stats_summary.avg_whip, 2)}</span>
                          </div>
                          <div className="flex justify-between">
                            <span>K/9:</span>
                            <span>{formatStat(candidate.baseline_stats_summary.avg_k9, 1)}</span>
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Recent Stats */}
                    <div className="bg-green-50 rounded-lg p-3">
                      <div className="text-xs font-medium text-green-700 mb-2">Recent Period</div>
                      {isHitter ? (
                        <div className="space-y-1 text-sm">
                          <div className="flex justify-between">
                            <span>AVG:</span>
                            <span className="font-medium text-green-700">
                              {formatStat(candidate.recent_stats_summary.avg_batting_avg)}
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span>OBP:</span>
                            <span className="font-medium text-green-700">
                              {formatStat(candidate.recent_stats_summary.avg_obp)}
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span>SLG:</span>
                            <span className="font-medium text-green-700">
                              {formatStat(candidate.recent_stats_summary.avg_slugging)}
                            </span>
                          </div>
                        </div>
                      ) : (
                        <div className="space-y-1 text-sm">
                          <div className="flex justify-between">
                            <span>ERA:</span>
                            <span className="font-medium text-green-700">
                              {formatStat(candidate.recent_stats_summary.avg_era, 2)}
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span>WHIP:</span>
                            <span className="font-medium text-green-700">
                              {formatStat(candidate.recent_stats_summary.avg_whip, 2)}
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span>K/9:</span>
                            <span className="font-medium text-green-700">
                              {formatStat(candidate.recent_stats_summary.avg_k9, 1)}
                            </span>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Analysis Summary */}
                <div className="bg-blue-50 rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-2">
                    <Calendar className="h-4 w-4 text-blue-600" />
                    <span className="text-sm font-medium text-blue-800">Analysis Summary</span>
                  </div>
                  <div className="text-sm text-blue-700">
                    <p>
                      {candidate.name} shows a{' '}
                      <strong>{formatPercentage(candidate.trend_indicators.max_improvement_rate)}</strong>{' '}
                      peak improvement rate with{' '}
                      <strong>{formatPercentage(candidate.trend_indicators.trend_consistency)}</strong>{' '}
                      consistency across <strong>{candidate.trend_indicators.data_points}</strong> data points.
                      {candidate.statistical_significance.confidence_level > 0.8 && (
                        ' This improvement shows high statistical confidence.'
                      )}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}