/**
 * Personalized Recommendations Component
 *
 * Displays prospect recommendations tailored to user's Fantrax league roster.
 *
 * @component PersonalizedRecommendations
 * @since 1.0.0
 */

'use client';

import React, { useEffect } from 'react';
import { useFantrax } from '@/hooks/useFantrax';
import type { ProspectRecommendation } from '@/types/fantrax';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, TrendingUp, Calendar, MapPin, BarChart3 } from 'lucide-react';

/**
 * Component props
 */
interface PersonalizedRecommendationsProps {
  /** Number of recommendations to display */
  limit?: number;
  /** Optional callback when prospect is clicked */
  onProspectClick?: (prospectId: number) => void;
  /** Whether to auto-load recommendations */
  autoLoad?: boolean;
}

/**
 * Personalized prospect recommendations component
 *
 * @param props - Component props
 * @returns Rendered component
 *
 * @example
 * ```tsx
 * <PersonalizedRecommendations
 *   limit={10}
 *   onProspectClick={(id) => router.push(`/prospects/${id}`)}
 *   autoLoad={true}
 * />
 * ```
 *
 * @since 1.0.0
 */
export function PersonalizedRecommendations({
  limit = 10,
  onProspectClick,
  autoLoad = true,
}: PersonalizedRecommendationsProps) {
  const {
    selectedLeague,
    recommendations,
    loading,
    error,
    loadRecommendations,
  } = useFantrax();

  // Auto-load recommendations when league is selected
  useEffect(() => {
    if (autoLoad && selectedLeague && recommendations.length === 0) {
      loadRecommendations(limit);
    }
  }, [
    autoLoad,
    selectedLeague,
    recommendations.length,
    loadRecommendations,
    limit,
  ]);

  /**
   * Get fit score color
   */
  const getFitScoreColor = (score: number): string => {
    if (score >= 80) return 'text-green-600 bg-green-50';
    if (score >= 60) return 'text-blue-600 bg-blue-50';
    if (score >= 40) return 'text-yellow-600 bg-yellow-50';
    return 'text-gray-600 bg-gray-50';
  };

  /**
   * Get trade value badge variant
   */
  const getTradeValueVariant = (value: string) => {
    const variants: Record<string, string> = {
      Elite: 'bg-purple-100 text-purple-800',
      High: 'bg-blue-100 text-blue-800',
      Medium: 'bg-green-100 text-green-800',
      Low: 'bg-gray-100 text-gray-800',
      Speculative: 'bg-orange-100 text-orange-800',
    };
    return variants[value] || variants['Low'];
  };

  if (!selectedLeague) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <BarChart3 className="h-12 w-12 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-600 mb-2">No league selected</p>
          <p className="text-sm text-gray-500">
            Select a league to view personalized prospect recommendations
          </p>
        </CardContent>
      </Card>
    );
  }

  if (loading.recommendations) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
          <span className="ml-2 text-gray-600">
            Generating recommendations...
          </span>
        </CardContent>
      </Card>
    );
  }

  if (error.recommendations) {
    return (
      <Card>
        <CardContent className="py-6">
          <Alert variant="destructive">
            <AlertDescription>{error.recommendations}</AlertDescription>
          </Alert>
          <Button onClick={() => loadRecommendations(limit)} className="mt-4">
            Try Again
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (recommendations.length === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <TrendingUp className="h-12 w-12 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-600 mb-2">No recommendations yet</p>
          <p className="text-sm text-gray-500 mb-4">
            Sync your roster to get personalized prospect recommendations
          </p>
          <Button onClick={() => loadRecommendations(limit)}>
            Load Recommendations
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Personalized Recommendations</CardTitle>
            <CardDescription>
              Prospects that best fit {selectedLeague.league_name}
            </CardDescription>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => loadRecommendations(limit)}
            disabled={loading.recommendations}
          >
            Refresh
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {recommendations.map((rec, index) => (
            <div
              key={rec.prospect_id}
              onClick={() => onProspectClick?.(rec.prospect_id)}
              className="p-4 rounded-lg border border-gray-200 hover:border-blue-300 hover:shadow-md transition-all cursor-pointer"
            >
              {/* Header with rank and fit score */}
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div className="flex items-center justify-center w-8 h-8 rounded-full bg-blue-100 text-blue-600 font-bold text-sm">
                    #{index + 1}
                  </div>
                  <div>
                    <h3 className="font-semibold text-gray-900">{rec.name}</h3>
                    <div className="flex items-center gap-2 mt-1">
                      <Badge variant="outline">{rec.position}</Badge>
                      {rec.age && (
                        <span className="text-xs text-gray-500">
                          {rec.age} years old
                        </span>
                      )}
                    </div>
                  </div>
                </div>
                <div
                  className={`px-3 py-1 rounded-full text-sm font-medium ${getFitScoreColor(rec.fit_score)}`}
                >
                  {rec.fit_score.toFixed(0)}% fit
                </div>
              </div>

              {/* Details */}
              <div className="grid grid-cols-2 gap-3 mb-3 text-sm">
                <div className="flex items-center gap-2 text-gray-600">
                  <MapPin className="h-4 w-4" />
                  <span>{rec.organization}</span>
                </div>
                <div className="flex items-center gap-2 text-gray-600">
                  <Calendar className="h-4 w-4" />
                  <span>ETA: {rec.eta_year}</span>
                </div>
              </div>

              {/* Trade Value */}
              <div className="mb-3">
                <Badge className={getTradeValueVariant(rec.trade_value)}>
                  {rec.trade_value} Value
                </Badge>
              </div>

              {/* Recommendation Reason */}
              <p className="text-sm text-gray-700 bg-gray-50 p-3 rounded">
                {rec.reason}
              </p>
            </div>
          ))}
        </div>

        {/* Load More */}
        {recommendations.length >= limit && (
          <div className="mt-4 text-center">
            <Button
              variant="outline"
              onClick={() => loadRecommendations(limit + 10)}
              disabled={loading.recommendations}
            >
              Load More
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
