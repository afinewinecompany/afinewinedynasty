/**
 * Recommendation Card Component
 *
 * Enhanced recommendation card with detailed fit score breakdown,
 * position fit, timeline fit, value rating, and expandable details.
 *
 * @component RecommendationCard
 * @since 1.0.0
 */

'use client';

import React, { useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  ChevronDown,
  ChevronUp,
  TrendingUp,
  Clock,
  DollarSign,
  Target,
} from 'lucide-react';
import type { RecommendationDetails } from '@/types/recommendations';

/**
 * Component props
 */
interface RecommendationCardProps {
  /** Recommendation data */
  recommendation: RecommendationDetails;
  /** Prospect name (from external data) */
  prospectName: string;
  /** Prospect position */
  position: string;
  /** Prospect organization */
  organization?: string;
  /** Expected MLB arrival year */
  etaYear?: number;
  /** Rank/index for display */
  rank?: number;
  /** Optional callback when card is clicked */
  onClick?: (prospectId: number) => void;
}

/**
 * Enhanced recommendation card component
 *
 * @param props - Component props
 * @returns Rendered component
 *
 * @example
 * ```tsx
 * <RecommendationCard
 *   recommendation={recommendation}
 *   prospectName="Jackson Holliday"
 *   position="SS"
 *   organization="BAL"
 *   etaYear={2024}
 *   rank={1}
 *   onClick={(id) => router.push(`/prospects/${id}`)}
 * />
 * ```
 *
 * @since 1.0.0
 */
export function RecommendationCard({
  recommendation,
  prospectName,
  position,
  organization,
  etaYear,
  rank,
  onClick,
}: RecommendationCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  /**
   * Get fit score color
   */
  const getFitScoreColor = (score: number): string => {
    if (score >= 80) return 'bg-green-50 text-green-700 border-green-200';
    if (score >= 60) return 'bg-blue-50 text-blue-700 border-blue-200';
    if (score >= 40) return 'bg-yellow-50 text-yellow-700 border-yellow-200';
    return 'bg-gray-50 text-gray-700 border-gray-200';
  };

  /**
   * Get confidence badge color
   */
  const getConfidenceColor = (
    confidence: RecommendationDetails['confidence']
  ): string => {
    const colors = {
      high: 'bg-green-100 text-green-800',
      medium: 'bg-blue-100 text-blue-800',
      low: 'bg-yellow-100 text-yellow-800',
    };
    return colors[confidence];
  };

  /**
   * Get value rating display
   */
  const getValueRating = (rating: RecommendationDetails['value_rating']) => {
    const ratings = {
      elite: { label: 'Elite', color: 'bg-purple-100 text-purple-800' },
      high: { label: 'High', color: 'bg-blue-100 text-blue-800' },
      medium: { label: 'Medium', color: 'bg-green-100 text-green-800' },
      low: { label: 'Low', color: 'bg-gray-100 text-gray-800' },
      speculative: {
        label: 'Speculative',
        color: 'bg-orange-100 text-orange-800',
      },
    };
    return ratings[rating];
  };

  /**
   * Get score percentage bar width
   */
  const getBarWidth = (score: number): string => {
    return `${Math.min(100, Math.max(0, score))}%`;
  };

  /**
   * Handle card click
   */
  const handleClick = () => {
    onClick?.(recommendation.prospect_id);
  };

  const valueRating = getValueRating(recommendation.value_rating);

  return (
    <Card
      className="w-full hover:shadow-md transition-all cursor-pointer"
      onClick={handleClick}
    >
      <CardContent className="p-4">
        {/* Header Section */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-start gap-3 flex-1">
            {/* Rank Badge */}
            {rank && (
              <div className="flex items-center justify-center w-10 h-10 rounded-full bg-blue-100 text-blue-700 font-bold text-sm flex-shrink-0">
                #{rank}
              </div>
            )}

            {/* Prospect Info */}
            <div className="flex-1 min-w-0">
              <h3 className="font-semibold text-gray-900 text-lg truncate">
                {prospectName}
              </h3>
              <div className="flex flex-wrap items-center gap-2 mt-1">
                <Badge variant="outline">{position}</Badge>
                {organization && (
                  <span className="text-sm text-gray-600">{organization}</span>
                )}
                {etaYear && (
                  <span className="text-xs text-gray-500">ETA: {etaYear}</span>
                )}
              </div>
            </div>
          </div>

          {/* Fit Score */}
          <div
            className={`px-4 py-2 rounded-lg border text-center flex-shrink-0 ml-3 ${getFitScoreColor(
              recommendation.fit_score
            )}`}
          >
            <div className="text-2xl font-bold">
              {recommendation.fit_score.toFixed(0)}
            </div>
            <div className="text-xs uppercase tracking-wide">Fit Score</div>
          </div>
        </div>

        {/* Fit Breakdown */}
        <div className="space-y-2 mb-3">
          {/* Position Fit */}
          <div className="flex items-center gap-2">
            <Target className="h-4 w-4 text-gray-500 flex-shrink-0" />
            <div className="flex-1">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium text-gray-700">
                  Position Fit
                </span>
                <span className="text-xs font-semibold text-gray-900">
                  {recommendation.position_fit.toFixed(0)}%
                </span>
              </div>
              <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500 transition-all"
                  style={{ width: getBarWidth(recommendation.position_fit) }}
                />
              </div>
            </div>
          </div>

          {/* Timeline Fit */}
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-gray-500 flex-shrink-0" />
            <div className="flex-1">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium text-gray-700">
                  Timeline Fit
                </span>
                <span className="text-xs font-semibold text-gray-900">
                  {recommendation.timeline_fit.toFixed(0)}%
                </span>
              </div>
              <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-green-500 transition-all"
                  style={{ width: getBarWidth(recommendation.timeline_fit) }}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Value Rating and Confidence */}
        <div className="flex items-center gap-2 mb-3">
          <DollarSign className="h-4 w-4 text-gray-500" />
          <Badge className={valueRating.color}>{valueRating.label} Value</Badge>
          <Badge className={getConfidenceColor(recommendation.confidence)}>
            {recommendation.confidence} confidence
          </Badge>
        </div>

        {/* Explanation */}
        <div className="p-3 rounded-lg bg-gray-50 mb-3">
          <p className="text-sm text-gray-700">{recommendation.explanation}</p>
        </div>

        {/* Expand/Collapse Toggle */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            setIsExpanded(!isExpanded);
          }}
          className="flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700 font-medium transition-colors"
        >
          {isExpanded ? (
            <>
              <ChevronUp className="h-4 w-4" />
              Show less
            </>
          ) : (
            <>
              <ChevronDown className="h-4 w-4" />
              Show detailed metrics
            </>
          )}
        </button>

        {/* Expanded Details */}
        {isExpanded && (
          <div className="mt-4 pt-4 border-t border-gray-200 space-y-3">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <div className="text-gray-600 mb-1">Overall Fit</div>
                <div className="font-semibold text-gray-900">
                  {recommendation.fit_score.toFixed(1)}%
                </div>
              </div>
              <div>
                <div className="text-gray-600 mb-1">Position Match</div>
                <div className="font-semibold text-gray-900">
                  {recommendation.position_fit.toFixed(1)}%
                </div>
              </div>
              <div>
                <div className="text-gray-600 mb-1">Timeline Match</div>
                <div className="font-semibold text-gray-900">
                  {recommendation.timeline_fit.toFixed(1)}%
                </div>
              </div>
              <div>
                <div className="text-gray-600 mb-1">Trade Value</div>
                <div className="font-semibold text-gray-900">
                  {valueRating.label}
                </div>
              </div>
            </div>

            {/* Confidence Indicator */}
            <div className="p-3 rounded-lg bg-blue-50 border border-blue-200">
              <div className="flex items-center gap-2 mb-1">
                <TrendingUp className="h-4 w-4 text-blue-600" />
                <span className="text-sm font-medium text-blue-900">
                  Recommendation Confidence
                </span>
              </div>
              <p className="text-xs text-blue-700">
                This recommendation has {recommendation.confidence} confidence
                based on your team's competitive timeline, positional needs, and
                prospect fit.
              </p>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
