'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { api } from '@/lib/api/client';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Eye,
  Clock,
  ExternalLink,
  User,
  Calendar,
  RotateCcw,
} from 'lucide-react';

/**
 * Represents a recently viewed prospect record
 *
 * @interface RecentlyViewedProspect
 * @since 1.0.0
 */
interface RecentlyViewedProspect {
  /** Unique identifier for the view record */
  id: number;
  /** ID of the prospect that was viewed */
  prospect_id: number;
  /** Name of the prospect for display */
  prospect_name: string;
  /** ISO timestamp when the prospect was viewed */
  viewed_at: string;
  /** Duration of the view in seconds, if tracked */
  view_duration: number | null;
}

/**
 * Recently Viewed Prospects Component
 *
 * Displays a sidebar widget showing user's recently viewed prospects for quick access
 * and research continuity. Automatically groups prospects by time periods and refreshes
 * every 30 seconds to show the most current viewing history.
 *
 * Features:
 * - Chronological list of recently viewed prospects (up to 15 entries)
 * - Quick links to prospect profiles
 * - View duration indicators showing engagement time
 * - Time-based organization (today, yesterday, this week, older)
 * - Research continuity support for seamless workflow
 * - Auto-refresh every 30 seconds
 * - Relative time display (e.g., "5m ago", "2h ago")
 *
 * @component
 * @returns {JSX.Element} Recently viewed prospects sidebar widget
 *
 * @example
 * ```tsx
 * <div className="sticky top-0">
 *   <RecentlyViewedProspects />
 * </div>
 * ```
 *
 * @since 1.0.0
 * @version 3.4.0
 */
export function RecentlyViewedProspects() {
  // Fetch recently viewed prospects
  const {
    data: recentlyViewed,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['recently-viewed-prospects'],
    queryFn: async () => {
      const response = await api.get('/search/recently-viewed?limit=15');
      return response.data as RecentlyViewedProspect[];
    },
    refetchInterval: 30000, // Refresh every 30 seconds to show recent views
  });

  const formatTimeAgo = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffInMinutes = Math.floor(
      (now.getTime() - date.getTime()) / (1000 * 60)
    );

    if (diffInMinutes < 1) {
      return 'Just now';
    } else if (diffInMinutes < 60) {
      return `${diffInMinutes}m ago`;
    } else {
      const diffInHours = Math.floor(diffInMinutes / 60);
      if (diffInHours < 24) {
        return `${diffInHours}h ago`;
      } else {
        const diffInDays = Math.floor(diffInHours / 24);
        return `${diffInDays}d ago`;
      }
    }
  };

  const formatViewDuration = (duration: number | null) => {
    if (!duration) return null;

    if (duration < 60) {
      return `${duration}s`;
    } else {
      const minutes = Math.floor(duration / 60);
      const seconds = duration % 60;
      return seconds > 0 ? `${minutes}m ${seconds}s` : `${minutes}m`;
    }
  };

  const groupViewsByTime = (views: RecentlyViewedProspect[]) => {
    const groups: { [key: string]: RecentlyViewedProspect[] } = {
      Today: [],
      Yesterday: [],
      'This Week': [],
      Older: [],
    };

    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    const weekAgo = new Date(today);
    weekAgo.setDate(weekAgo.getDate() - 7);

    views.forEach((view) => {
      const viewDate = new Date(view.viewed_at);
      const viewDateOnly = new Date(
        viewDate.getFullYear(),
        viewDate.getMonth(),
        viewDate.getDate()
      );

      if (viewDateOnly.getTime() === today.getTime()) {
        groups['Today'].push(view);
      } else if (viewDateOnly.getTime() === yesterday.getTime()) {
        groups['Yesterday'].push(view);
      } else if (viewDate > weekAgo) {
        groups['This Week'].push(view);
      } else {
        groups['Older'].push(view);
      }
    });

    // Filter out empty groups
    return Object.entries(groups).filter(([_, views]) => views.length > 0);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-6">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-6">
        <div className="text-red-500 text-sm mb-3">
          Failed to load recent views
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => window.location.reload()}
        >
          <RotateCcw className="h-3 w-3 mr-1" />
          Retry
        </Button>
      </div>
    );
  }

  if (!recentlyViewed || recentlyViewed.length === 0) {
    return (
      <div className="text-center py-6">
        <Eye className="h-8 w-8 text-gray-300 mx-auto mb-3" />
        <h4 className="text-sm font-medium text-gray-900 mb-1">
          No recent views
        </h4>
        <p className="text-xs text-gray-500">
          Prospects you view will appear here for quick access
        </p>
      </div>
    );
  }

  const groupedViews = groupViewsByTime(recentlyViewed);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-medium text-gray-900">Recent Views</h4>
        <Badge variant="outline" className="text-xs">
          {recentlyViewed.length}
        </Badge>
      </div>

      <div className="space-y-4">
        {groupedViews.map(([groupName, views]) => (
          <div key={groupName} className="space-y-2">
            <h5 className="text-xs font-medium text-gray-600 flex items-center gap-1">
              <Calendar className="h-3 w-3" />
              {groupName}
            </h5>

            <div className="space-y-2">
              {views.map((view) => (
                <Card
                  key={view.id}
                  className="hover:shadow-sm transition-shadow"
                >
                  <CardContent className="p-3">
                    <div className="space-y-2">
                      <div className="flex items-start justify-between">
                        <Link
                          href={`/prospects/${view.prospect_id}`}
                          className="flex-1 min-w-0"
                        >
                          <div className="flex items-center gap-1 mb-1">
                            <User className="h-3 w-3 text-gray-400 flex-shrink-0" />
                            <span className="text-sm font-medium text-gray-900 truncate">
                              {view.prospect_name}
                            </span>
                          </div>
                        </Link>
                        <Link
                          href={`/prospects/${view.prospect_id}`}
                          className="ml-2"
                        >
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-6 w-6 p-0"
                          >
                            <ExternalLink className="h-3 w-3" />
                          </Button>
                        </Link>
                      </div>

                      <div className="flex items-center justify-between text-xs text-gray-500">
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {formatTimeAgo(view.viewed_at)}
                        </span>
                        {view.view_duration && (
                          <Badge variant="secondary" className="text-xs">
                            {formatViewDuration(view.view_duration)}
                          </Badge>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        ))}
      </div>

      {recentlyViewed.length >= 15 && (
        <div className="text-center pt-2">
          <Link
            href="/prospects/recently-viewed"
            className="text-xs text-blue-600 hover:text-blue-700"
          >
            View all recent prospects →
          </Link>
        </div>
      )}
    </div>
  );
}
