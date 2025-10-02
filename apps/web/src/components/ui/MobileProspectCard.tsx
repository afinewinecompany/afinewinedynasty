/**
 * Mobile-optimized prospect card component with priority information display
 *
 * @component MobileProspectCard
 * @since 1.0.0
 */

import React from 'react';
import Link from 'next/link';
import { Card, CardContent } from './card';
import { Badge } from './badge';
import { Button } from './button';
import type { ProspectRanking } from '@/types/prospect';

/**
 * Props for the MobileProspectCard component
 *
 * @interface MobileProspectCardProps
 */
interface MobileProspectCardProps {
  /** The prospect ranking data to display */
  prospect: ProspectRanking;

  /** Callback when quick action is triggered */
  onQuickAction?: (action: 'compare' | 'watchlist', prospectId: string) => void;

  /** Whether the prospect is in watchlist */
  isInWatchlist?: boolean;

  /** Additional CSS classes */
  className?: string;
}

/**
 * Mobile-optimized prospect card with streamlined information hierarchy
 *
 * Priority 1 info always visible, Priority 2/3 accessible through progressive disclosure
 * Minimum touch targets of 44px for all interactive elements
 *
 * @param {MobileProspectCardProps} props - Component props
 * @returns {JSX.Element} Rendered mobile prospect card
 *
 * @example
 * ```tsx
 * <MobileProspectCard
 *   prospect={prospectData}
 *   onQuickAction={handleQuickAction}
 *   isInWatchlist={false}
 * />
 * ```
 */
export const MobileProspectCard: React.FC<MobileProspectCardProps> = ({
  prospect,
  onQuickAction,
  isInWatchlist = false,
  className = ''
}) => {
  const [isExpanded, setIsExpanded] = React.useState(false);

  const handleQuickAction = (action: 'compare' | 'watchlist') => {
    onQuickAction?.(action, prospect.id);
  };

  // Format confidence percentage
  const confidencePercent = Math.round((prospect.mlPrediction?.confidence || 0) * 100);

  // Determine confidence color
  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 80) return 'text-green-600';
    if (confidence >= 60) return 'text-yellow-600';
    return 'text-red-600';
  };

  return (
    <Card className={`mb-3 ${className}`}>
      <CardContent className="p-3">
        {/* Priority 1 Information - Always Visible */}
        <div className="flex items-start justify-between">
          <Link href={`/prospects/${prospect.id}`} className="flex-1">
            <div className="flex items-center gap-3">
              {/* Rank Badge */}
              <div className="flex-shrink-0">
                <Badge variant="outline" className="text-lg font-bold min-w-[44px] h-[44px] flex items-center justify-center">
                  #{prospect.rank}
                </Badge>
              </div>

              {/* Name and Position */}
              <div className="flex-1 min-w-0">
                <h3 className="font-semibold text-base truncate">
                  {prospect.name}
                </h3>
                <div className="flex items-center gap-2 text-sm text-gray-600">
                  <span>{prospect.position}</span>
                  <span>•</span>
                  <span>{prospect.organization}</span>
                </div>

                {/* ML Prediction & ETA */}
                <div className="flex items-center gap-3 mt-1">
                  <span className={`text-sm font-medium ${getConfidenceColor(confidencePercent)}`}>
                    {confidencePercent}% confidence
                  </span>
                  <Badge variant="secondary" className="text-xs">
                    ETA {prospect.eta}
                  </Badge>
                </div>
              </div>
            </div>
          </Link>

          {/* Quick Actions */}
          <div className="flex flex-col gap-1">
            <Button
              size="sm"
              variant={isInWatchlist ? "default" : "outline"}
              className="min-w-[44px] h-[44px] p-2"
              onClick={() => handleQuickAction('watchlist')}
              aria-label={isInWatchlist ? "Remove from watchlist" : "Add to watchlist"}
            >
              {isInWatchlist ? '★' : '☆'}
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="min-w-[44px] h-[44px] p-2"
              onClick={() => handleQuickAction('compare')}
              aria-label="Add to comparison"
            >
              ⚖
            </Button>
          </div>
        </div>

        {/* Priority 2 Information - Expandable */}
        {!isExpanded && (
          <button
            onClick={() => setIsExpanded(true)}
            className="w-full mt-3 text-sm text-blue-600 font-medium text-left min-h-[44px] flex items-center"
            aria-label="Show more details"
          >
            View stats & details ▼
          </button>
        )}

        {isExpanded && (
          <div className="mt-3 pt-3 border-t border-gray-200">
            {/* Current Season Stats */}
            <div className="mb-3">
              <h4 className="text-sm font-semibold mb-1">Current Season</h4>
              <div className="grid grid-cols-3 gap-2 text-sm">
                <div>
                  <span className="text-gray-600">AVG:</span> {prospect.stats?.battingAverage || '--'}
                </div>
                <div>
                  <span className="text-gray-600">OPS:</span> {prospect.stats?.ops || '--'}
                </div>
                <div>
                  <span className="text-gray-600">HR:</span> {prospect.stats?.homeRuns || '--'}
                </div>
              </div>
            </div>

            {/* Scouting Grades */}
            {prospect.scoutingGrades && (
              <div className="mb-3">
                <h4 className="text-sm font-semibold mb-1">Scouting Grades</h4>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <span className="text-gray-600">Hit:</span> {prospect.scoutingGrades.hit}/80
                  </div>
                  <div>
                    <span className="text-gray-600">Power:</span> {prospect.scoutingGrades.power}/80
                  </div>
                  <div>
                    <span className="text-gray-600">Speed:</span> {prospect.scoutingGrades.speed}/80
                  </div>
                  <div>
                    <span className="text-gray-600">Field:</span> {prospect.scoutingGrades.fielding}/80
                  </div>
                </div>
              </div>
            )}

            {/* AI Outlook */}
            {prospect.aiOutlook && (
              <div className="mb-3">
                <h4 className="text-sm font-semibold mb-1">AI Outlook</h4>
                <p className="text-sm text-gray-700 line-clamp-2">
                  {prospect.aiOutlook}
                </p>
              </div>
            )}

            <button
              onClick={() => setIsExpanded(false)}
              className="w-full text-sm text-blue-600 font-medium text-left min-h-[44px] flex items-center"
              aria-label="Show less details"
            >
              Show less ▲
            </button>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default MobileProspectCard;