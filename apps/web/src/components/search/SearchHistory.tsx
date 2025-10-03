'use client';

import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api/client';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { AdvancedSearchCriteria } from '@/hooks/useAdvancedSearch';
import {
  History,
  Search,
  Calendar,
  Filter,
  Play,
  Clock,
  RotateCcw,
} from 'lucide-react';

/**
 * Represents a search history entry record
 *
 * @interface SearchHistoryEntry
 * @since 1.0.0
 */
interface SearchHistoryEntry {
  /** Unique identifier for the history entry */
  id: number;
  /** Text search query if applicable */
  search_query: string | null;
  /** Complete search criteria object */
  search_criteria: any;
  /** Number of results returned from this search */
  results_count: number | null;
  /** ISO timestamp when the search was executed */
  searched_at: string;
}

/**
 * Props for the SearchHistory component
 *
 * @interface SearchHistoryProps
 * @since 1.0.0
 */
interface SearchHistoryProps {
  /** Callback triggered when user selects a history item to re-execute */
  onHistoryItemSelect: (historyItem: SearchHistoryEntry) => void;
}

/**
 * Search History Component
 *
 * Displays user's recent search history with quick re-execution capability.
 * Automatically groups searches by time periods (today, yesterday, this week, etc.)
 * and provides visual previews of search criteria for easy identification.
 *
 * Features:
 * - Chronological list of recent searches (up to 50 entries)
 * - Visual preview of search criteria with filter badges
 * - Result count indicators for each search
 * - One-click re-execution of past searches
 * - Time-based organization with smart grouping
 * - Quick access to frequently used searches
 * - Relative time display (e.g., "5 minutes ago")
 * - Automatic refresh from backend
 *
 * @component
 * @param {SearchHistoryProps} props - Component properties
 * @returns {JSX.Element} Search history interface with grouped timeline
 *
 * @example
 * ```tsx
 * <SearchHistory
 *   onHistoryItemSelect={(historyItem) => {
 *     setCriteria(historyItem.search_criteria);
 *     performSearch();
 *   }}
 * />
 * ```
 *
 * @since 1.0.0
 * @version 3.4.0
 */
export function SearchHistory({ onHistoryItemSelect }: SearchHistoryProps) {
  // Fetch search history
  const {
    data: searchHistory,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['search-history'],
    queryFn: async () => {
      const response = await api.get('/search/history?limit=50');
      return response.data as SearchHistoryEntry[];
    },
  });

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffInHours = Math.floor(
      (now.getTime() - date.getTime()) / (1000 * 60 * 60)
    );

    if (diffInHours < 1) {
      const diffInMinutes = Math.floor(
        (now.getTime() - date.getTime()) / (1000 * 60)
      );
      return `${diffInMinutes} minute${diffInMinutes !== 1 ? 's' : ''} ago`;
    } else if (diffInHours < 24) {
      return `${diffInHours} hour${diffInHours !== 1 ? 's' : ''} ago`;
    } else {
      const diffInDays = Math.floor(diffInHours / 24);
      if (diffInDays < 7) {
        return `${diffInDays} day${diffInDays !== 1 ? 's' : ''} ago`;
      } else {
        return date.toLocaleDateString('en-US', {
          month: 'short',
          day: 'numeric',
          year:
            date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
        });
      }
    }
  };

  const getActiveFiltersCount = (criteria: any) => {
    if (!criteria) return 0;
    const { page, size, sort_by, ...filters } = criteria;
    return Object.values(filters).filter((value) => {
      if (Array.isArray(value)) return value.length > 0;
      return value !== undefined && value !== null && value !== '';
    }).length;
  };

  const getCriteriaPreview = (criteria: any, searchQuery: string | null) => {
    const previews = [];

    if (searchQuery) {
      previews.push(
        <Badge key="query" variant="secondary" className="text-xs">
          <Search className="h-3 w-3 mr-1" />"{searchQuery}"
        </Badge>
      );
    }

    if (!criteria) return previews;

    // Basic filters
    if (criteria.basic?.positions && criteria.basic.positions.length > 0) {
      const positions = criteria.basic.positions;
      previews.push(
        <Badge key="positions" variant="secondary" className="text-xs">
          Positions: {positions.slice(0, 2).join(', ')}
          {positions.length > 2 && ` +${positions.length - 2} more`}
        </Badge>
      );
    }

    if (criteria.basic?.min_age || criteria.basic?.max_age) {
      const ageRange = [
        criteria.basic.min_age ? `${criteria.basic.min_age}+` : '',
        criteria.basic.max_age ? `≤${criteria.basic.max_age}` : '',
      ]
        .filter(Boolean)
        .join(' ');
      previews.push(
        <Badge key="age" variant="secondary" className="text-xs">
          Age: {ageRange}
        </Badge>
      );
    }

    // Statistical filters
    if (criteria.statistical?.min_batting_avg) {
      previews.push(
        <Badge key="batting-avg" variant="secondary" className="text-xs">
          BA ≥ {criteria.statistical.min_batting_avg}
        </Badge>
      );
    }

    if (criteria.statistical?.max_era) {
      previews.push(
        <Badge key="era" variant="secondary" className="text-xs">
          ERA ≤ {criteria.statistical.max_era}
        </Badge>
      );
    }

    // Scouting filters
    if (criteria.scouting?.min_overall_grade) {
      previews.push(
        <Badge key="grade" variant="secondary" className="text-xs">
          Grade ≥ {criteria.scouting.min_overall_grade}
        </Badge>
      );
    }

    // ML filters
    if (criteria.ml?.min_success_probability) {
      previews.push(
        <Badge key="ml" variant="secondary" className="text-xs">
          ML Success ≥ {Math.round(criteria.ml.min_success_probability * 100)}%
        </Badge>
      );
    }

    return previews.slice(0, 4); // Limit to 4 previews to prevent overflow
  };

  const groupHistoryByDate = (history: SearchHistoryEntry[]) => {
    const groups: { [key: string]: SearchHistoryEntry[] } = {};
    const now = new Date();

    history.forEach((entry) => {
      const entryDate = new Date(entry.searched_at);
      const diffInDays = Math.floor(
        (now.getTime() - entryDate.getTime()) / (1000 * 60 * 60 * 24)
      );

      let groupKey: string;
      if (diffInDays === 0) {
        groupKey = 'Today';
      } else if (diffInDays === 1) {
        groupKey = 'Yesterday';
      } else if (diffInDays < 7) {
        groupKey = `${diffInDays} days ago`;
      } else {
        groupKey = entryDate.toLocaleDateString('en-US', {
          month: 'long',
          year:
            entryDate.getFullYear() !== now.getFullYear()
              ? 'numeric'
              : undefined,
        });
      }

      if (!groups[groupKey]) {
        groups[groupKey] = [];
      }
      groups[groupKey].push(entry);
    });

    return groups;
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-8">
        <div className="text-red-500 mb-4">Failed to load search history</div>
        <Button variant="outline" onClick={() => window.location.reload()}>
          <RotateCcw className="h-4 w-4 mr-2" />
          Retry
        </Button>
      </div>
    );
  }

  if (!searchHistory || searchHistory.length === 0) {
    return (
      <div className="text-center py-8">
        <History className="h-12 w-12 text-gray-300 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-900 mb-2">
          No search history yet
        </h3>
        <p className="text-gray-500">
          Your recent searches will appear here for quick access
        </p>
      </div>
    );
  }

  const groupedHistory = groupHistoryByDate(searchHistory);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium">Search History</h3>
        <Badge variant="outline" className="text-xs">
          {searchHistory.length} search{searchHistory.length !== 1 ? 'es' : ''}
        </Badge>
      </div>

      {Object.entries(groupedHistory).map(([groupName, entries]) => (
        <div key={groupName} className="space-y-3">
          <h4 className="text-sm font-medium text-gray-700 flex items-center gap-2">
            <Calendar className="h-4 w-4" />
            {groupName}
          </h4>

          <div className="space-y-2">
            {entries.map((entry) => {
              const filtersCount = getActiveFiltersCount(entry.search_criteria);
              const previews = getCriteriaPreview(
                entry.search_criteria,
                entry.search_query
              );

              return (
                <Card
                  key={entry.id}
                  className="hover:shadow-sm transition-shadow"
                >
                  <CardContent className="p-3">
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-2">
                          <Filter className="h-4 w-4 text-gray-400 flex-shrink-0" />
                          {filtersCount > 0 ? (
                            <Badge variant="outline" className="text-xs">
                              {filtersCount} filter
                              {filtersCount !== 1 ? 's' : ''}
                            </Badge>
                          ) : (
                            <span className="text-sm text-gray-500">
                              Empty search
                            </span>
                          )}
                          {entry.results_count !== null && (
                            <Badge variant="secondary" className="text-xs">
                              {entry.results_count} result
                              {entry.results_count !== 1 ? 's' : ''}
                            </Badge>
                          )}
                          <span className="text-xs text-gray-400 flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {formatDate(entry.searched_at)}
                          </span>
                        </div>

                        {previews.length > 0 && (
                          <div className="flex flex-wrap gap-1 mb-2">
                            {previews}
                            {filtersCount > previews.length && (
                              <Badge variant="outline" className="text-xs">
                                +{filtersCount - previews.length} more
                              </Badge>
                            )}
                          </div>
                        )}
                      </div>

                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onHistoryItemSelect(entry)}
                        className="flex items-center gap-1 ml-2 flex-shrink-0"
                        disabled={!entry.search_criteria}
                      >
                        <Play className="h-3 w-3" />
                        Run
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
