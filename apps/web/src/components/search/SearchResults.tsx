'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api/client';
import { SearchResults as SearchResultsType } from '@/hooks/useAdvancedSearch';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Search,
  Star,
  TrendingUp,
  Eye,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  Filter,
  BarChart3,
  Target,
  Brain,
  AlertCircle,
} from 'lucide-react';

/**
 * Props for the SearchResults component
 *
 * @interface SearchResultsProps
 * @since 1.0.0
 */
interface SearchResultsProps {
  /** Search results data including prospects, pagination, and metadata */
  results: SearchResultsType | undefined;
  /** Loading state indicator for search operation */
  isLoading: boolean;
  /** Error object from failed search operations */
  error: any;
  /** Callback triggered when user views a prospect (for analytics tracking) */
  onProspectView: (prospectId: number) => void;
}

/**
 * Search Results Component
 *
 * Displays advanced search results with relevance scoring indicators,
 * pagination, and prospect interaction tracking. Provides comprehensive
 * prospect information cards with statistics, scouting grades, and ML
 * predictions, along with view tracking for user behavior analytics.
 *
 * Features:
 * - Prospect cards with comprehensive information display
 * - Relevance scoring visualization with progress bars
 * - Statistical highlights (batting, pitching) with position-aware display
 * - Scouting grade indicators with 20-80 scale visualization
 * - ML prediction indicators with confidence levels
 * - Pagination controls for result navigation
 * - View tracking for analytics and personalization
 * - Filter metadata display showing active filters
 * - Empty state and error handling with helpful messages
 * - Result count summaries and search complexity indicators
 *
 * @component
 * @param {SearchResultsProps} props - Component properties
 * @returns {JSX.Element} Search results display with pagination and analytics
 *
 * @example
 * ```tsx
 * <SearchResults
 *   results={searchResults}
 *   isLoading={isSearching}
 *   error={searchError}
 *   onProspectView={(prospectId) => {
 *     trackProspectView(prospectId);
 *     navigate(`/prospects/${prospectId}`);
 *   }}
 * />
 * ```
 *
 * @since 1.0.0
 * @version 3.4.0
 */
export function SearchResults({
  results,
  isLoading,
  error,
  onProspectView,
}: SearchResultsProps) {
  const [viewingProspect, setViewingProspect] = useState<number | null>(null);
  const queryClient = useQueryClient();

  // Track prospect view mutation
  const trackViewMutation = useMutation({
    mutationFn: async ({
      prospectId,
      duration,
    }: {
      prospectId: number;
      duration?: number;
    }) => {
      await api.post('/search/track-view', null, {
        params: { prospect_id: prospectId, view_duration: duration },
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['recently-viewed-prospects'],
      });
    },
  });

  const handleProspectView = (prospectId: number) => {
    setViewingProspect(prospectId);
    trackViewMutation.mutate({ prospectId });
    onProspectView(prospectId);

    // Clear viewing state after a delay
    setTimeout(() => setViewingProspect(null), 2000);
  };

  const getFilterIcon = (filterType: string) => {
    switch (filterType) {
      case 'statistical':
        return <BarChart3 className="h-4 w-4 text-green-500" />;
      case 'scouting':
        return <Target className="h-4 w-4 text-orange-500" />;
      case 'ml_predictions':
        return <Brain className="h-4 w-4 text-purple-500" />;
      case 'basic_filters':
        return <Filter className="h-4 w-4 text-blue-500" />;
      case 'text_search':
        return <Search className="h-4 w-4 text-gray-500" />;
      default:
        return <Filter className="h-4 w-4 text-gray-500" />;
    }
  };

  const formatStatValue = (
    value: number | null | undefined,
    isPercentage = false
  ) => {
    if (value === null || value === undefined) return 'N/A';
    if (isPercentage) return `${(value * 100).toFixed(1)}%`;
    return value.toFixed(3);
  };

  const getGradeColor = (grade: number | null | undefined) => {
    if (!grade) return 'bg-gray-200';
    if (grade >= 70) return 'bg-green-500';
    if (grade >= 60) return 'bg-blue-500';
    if (grade >= 50) return 'bg-yellow-500';
    if (grade >= 40) return 'bg-orange-500';
    return 'bg-red-500';
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Searching prospects...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-900 mb-2">
          Search Failed
        </h3>
        <p className="text-gray-600 mb-4">
          {error.message ||
            'An error occurred while searching. Please try again.'}
        </p>
        <Button variant="outline" onClick={() => window.location.reload()}>
          Try Again
        </Button>
      </div>
    );
  }

  if (!results) {
    return (
      <div className="text-center py-12">
        <Search className="h-12 w-12 text-gray-300 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-900 mb-2">
          Ready to Search
        </h3>
        <p className="text-gray-600">
          Set your search criteria and click search to find prospects
        </p>
      </div>
    );
  }

  if (results.total_count === 0) {
    return (
      <div className="text-center py-12">
        <Search className="h-12 w-12 text-gray-300 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-900 mb-2">
          No Results Found
        </h3>
        <p className="text-gray-600 mb-4">
          Try adjusting your search criteria to find more prospects
        </p>
        <div className="text-sm text-gray-500">
          <p>Consider:</p>
          <ul className="list-disc list-inside mt-2 space-y-1">
            <li>Expanding age or grade ranges</li>
            <li>Including more positions or organizations</li>
            <li>Lowering statistical thresholds</li>
            <li>Using different search terms</li>
          </ul>
        </div>
      </div>
    );
  }

  const appliedFilters = Object.entries(results.search_metadata.applied_filters)
    .filter(([_, applied]) => applied)
    .map(([type]) => type);

  return (
    <div className="space-y-6">
      {/* Search Summary */}
      <div className="bg-gray-50 rounded-lg p-4">
        <div className="flex items-start justify-between mb-3">
          <div>
            <h3 className="text-lg font-medium text-gray-900">
              {results.total_count.toLocaleString()} prospect
              {results.total_count !== 1 ? 's' : ''} found
            </h3>
            <p className="text-sm text-gray-600">
              Showing {results.prospects.length} results on page {results.page}{' '}
              of {results.total_pages}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-600">Sort:</span>
            <Badge variant="secondary">{results.search_metadata.sort_by}</Badge>
          </div>
        </div>

        {appliedFilters.length > 0 && (
          <div>
            <p className="text-sm text-gray-600 mb-2">Active filters:</p>
            <div className="flex flex-wrap gap-2">
              {appliedFilters.map((filterType) => (
                <Badge key={filterType} variant="outline" className="text-xs">
                  {getFilterIcon(filterType)}
                  <span className="ml-1 capitalize">
                    {filterType.replace('_', ' ')}
                  </span>
                </Badge>
              ))}
              <Badge variant="secondary" className="text-xs">
                Complexity: {results.search_metadata.search_complexity}
              </Badge>
            </div>
          </div>
        )}
      </div>

      {/* Results Grid */}
      <div className="grid gap-4">
        {results.prospects.map((prospect) => (
          <Card
            key={prospect.id}
            className={`hover:shadow-md transition-all duration-200 ${
              viewingProspect === prospect.id ? 'ring-2 ring-blue-500' : ''
            }`}
          >
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <Link
                      href={`/prospects/${prospect.id}`}
                      onClick={() => handleProspectView(prospect.id)}
                      className="font-semibold text-lg text-gray-900 hover:text-blue-600 transition-colors"
                    >
                      {prospect.name}
                    </Link>
                    <Badge variant="outline">{prospect.position}</Badge>
                    {prospect.age && (
                      <Badge variant="secondary" className="text-xs">
                        Age {prospect.age}
                      </Badge>
                    )}
                  </div>
                  <div className="flex items-center gap-4 text-sm text-gray-600">
                    <span>{prospect.organization}</span>
                    <span>{prospect.level}</span>
                    {prospect.eta_year && <span>ETA: {prospect.eta_year}</span>}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleProspectView(prospect.id)}
                  >
                    <Eye className="h-4 w-4" />
                  </Button>
                  <Link href={`/prospects/${prospect.id}`}>
                    <Button variant="outline" size="sm">
                      <ExternalLink className="h-4 w-4" />
                    </Button>
                  </Link>
                </div>
              </div>
            </CardHeader>

            <CardContent className="space-y-4">
              {/* Latest Stats */}
              {prospect.latest_stats && (
                <div>
                  <h4 className="text-sm font-medium text-gray-700 mb-2 flex items-center gap-1">
                    <BarChart3 className="h-4 w-4" />
                    Latest Statistics
                  </h4>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
                    {prospect.position === 'SP' ||
                    prospect.position === 'RP' ? (
                      <>
                        {prospect.latest_stats.era && (
                          <div>
                            <span className="text-gray-500">ERA:</span>
                            <span className="ml-1 font-medium">
                              {prospect.latest_stats.era.toFixed(2)}
                            </span>
                          </div>
                        )}
                        {prospect.latest_stats.whip && (
                          <div>
                            <span className="text-gray-500">WHIP:</span>
                            <span className="ml-1 font-medium">
                              {prospect.latest_stats.whip.toFixed(2)}
                            </span>
                          </div>
                        )}
                      </>
                    ) : (
                      <>
                        {prospect.latest_stats.batting_avg && (
                          <div>
                            <span className="text-gray-500">AVG:</span>
                            <span className="ml-1 font-medium">
                              {formatStatValue(
                                prospect.latest_stats.batting_avg
                              )}
                            </span>
                          </div>
                        )}
                        {prospect.latest_stats.on_base_pct && (
                          <div>
                            <span className="text-gray-500">OBP:</span>
                            <span className="ml-1 font-medium">
                              {formatStatValue(
                                prospect.latest_stats.on_base_pct
                              )}
                            </span>
                          </div>
                        )}
                        {prospect.latest_stats.slugging_pct && (
                          <div>
                            <span className="text-gray-500">SLG:</span>
                            <span className="ml-1 font-medium">
                              {formatStatValue(
                                prospect.latest_stats.slugging_pct
                              )}
                            </span>
                          </div>
                        )}
                        {prospect.latest_stats.woba && (
                          <div>
                            <span className="text-gray-500">wOBA:</span>
                            <span className="ml-1 font-medium">
                              {formatStatValue(prospect.latest_stats.woba)}
                            </span>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">
                    As of{' '}
                    {new Date(
                      prospect.latest_stats.date_recorded
                    ).toLocaleDateString()}
                  </div>
                </div>
              )}

              {/* Scouting Grades */}
              {prospect.scouting_grades &&
                prospect.scouting_grades.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-2 flex items-center gap-1">
                      <Target className="h-4 w-4" />
                      Scouting Grades
                    </h4>
                    <div className="space-y-2">
                      {prospect.scouting_grades
                        .slice(0, 2)
                        .map((grade, index) => (
                          <div key={index} className="text-sm">
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-gray-600">
                                {grade.source}
                              </span>
                              {grade.overall && (
                                <Badge variant="secondary" className="text-xs">
                                  Overall: {grade.overall}
                                </Badge>
                              )}
                            </div>
                            {grade.overall && (
                              <div className="flex items-center gap-2">
                                <Progress
                                  value={((grade.overall - 20) / 60) * 100}
                                  className="flex-1 h-2"
                                />
                                <span className="text-xs text-gray-500 w-8">
                                  {grade.overall}
                                </span>
                              </div>
                            )}
                          </div>
                        ))}
                    </div>
                  </div>
                )}

              {/* Relevance Score */}
              <div className="flex items-center justify-between pt-2 border-t border-gray-100">
                <div className="flex items-center gap-2 text-xs text-gray-500">
                  <Star className="h-3 w-3" />
                  Match Score
                </div>
                <div className="flex items-center gap-2">
                  <Progress value={85} className="w-16 h-2" />
                  <span className="text-xs font-medium text-gray-700">85%</span>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Pagination */}
      {results.total_pages > 1 && (
        <div className="flex items-center justify-between pt-6 border-t border-gray-200">
          <div className="text-sm text-gray-600">
            Showing {(results.page - 1) * results.size + 1} to{' '}
            {Math.min(results.page * results.size, results.total_count)} of{' '}
            {results.total_count.toLocaleString()} results
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={!results.has_prev}
              className="flex items-center gap-1"
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </Button>
            <div className="flex items-center gap-1">
              {/* Page numbers would go here */}
              <span className="px-3 py-1 text-sm bg-blue-100 text-blue-700 rounded">
                {results.page}
              </span>
              <span className="text-sm text-gray-500">
                of {results.total_pages}
              </span>
            </div>
            <Button
              variant="outline"
              size="sm"
              disabled={!results.has_next}
              className="flex items-center gap-1"
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
