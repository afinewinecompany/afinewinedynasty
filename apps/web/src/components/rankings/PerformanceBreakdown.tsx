'use client';

import React from 'react';
import { CompositeRanking } from '@/types/prospect';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { Info, Database, TrendingUp } from 'lucide-react';

interface PerformanceBreakdownProps {
  prospect: CompositeRanking;
  compact?: boolean;
}

export default function PerformanceBreakdown({ prospect, compact = false }: PerformanceBreakdownProps) {
  const breakdown = prospect.performance_breakdown;

  if (!breakdown) {
    return (
      <div className="text-xs text-muted-foreground italic">
        No performance data available
      </div>
    );
  }

  const getSourceLabel = (source: string) => {
    switch (source) {
      case 'pitch_data':
        return 'Pitch Data';
      case 'game_logs':
        return 'Game Logs';
      case 'insufficient_data':
        return 'Limited Data';
      case 'no_data':
        return 'No Data';
      default:
        return source;
    }
  };

  const getSourceColor = (source: string) => {
    switch (source) {
      case 'pitch_data':
        return 'bg-green-100 text-green-800 border-green-200';
      case 'game_logs':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'insufficient_data':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'no_data':
        return 'bg-gray-100 text-gray-800 border-gray-200';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getPercentileColor = (percentile: number) => {
    if (percentile >= 90) return 'text-green-700 font-bold';
    if (percentile >= 75) return 'text-green-600 font-semibold';
    if (percentile >= 60) return 'text-blue-600 font-medium';
    if (percentile >= 40) return 'text-gray-600';
    if (percentile >= 25) return 'text-orange-600';
    return 'text-red-600 font-medium';
  };

  const getPercentileBar = (percentile: number) => {
    const width = Math.max(0, Math.min(100, percentile));
    let bgColor = 'bg-gray-400';
    if (percentile >= 75) bgColor = 'bg-green-500';
    else if (percentile >= 50) bgColor = 'bg-blue-500';
    else if (percentile >= 25) bgColor = 'bg-yellow-500';
    else bgColor = 'bg-red-500';

    return (
      <div className="w-full bg-gray-200 rounded-full h-1.5 overflow-hidden">
        <div
          className={`${bgColor} h-full transition-all duration-300`}
          style={{ width: `${width}%` }}
        />
      </div>
    );
  };

  const formatMetricName = (metric: string) => {
    const names: Record<string, string> = {
      exit_velo_90th: 'Exit Velo (90th %ile)',
      hard_hit_rate: 'Hard Hit Rate',
      contact_rate: 'Contact Rate',
      whiff_rate: 'Whiff Rate',
      chase_rate: 'Chase Rate',
      zone_rate: 'Zone Rate',
      avg_fb_velo: 'Avg FB Velocity',
      hard_contact_rate: 'Hard Contact Allowed',
      ops: 'OPS',
      k_minus_bb: 'K% - BB%',
    };
    return names[metric] || metric;
  };

  const isPitcher = prospect.position === 'SP' || prospect.position === 'RP' || prospect.position === 'P';

  // Compact version - just show source badge and composite percentile
  if (compact) {
    return (
      <div className="flex items-center gap-2">
        <span className={`px-2 py-0.5 text-xs font-medium rounded border ${getSourceColor(breakdown.source)}`}>
          {getSourceLabel(breakdown.source)}
        </span>
        {breakdown.composite_percentile !== undefined && (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger>
                <span className={`text-xs ${getPercentileColor(breakdown.composite_percentile)}`}>
                  {breakdown.composite_percentile.toFixed(0)}%ile
                </span>
              </TooltipTrigger>
              <TooltipContent className="bg-popover border-border">
                <p className="text-xs text-popover-foreground">
                  Performance vs level peers
                  {breakdown.sample_size && ` (${breakdown.sample_size} pitches)`}
                </p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}
      </div>
    );
  }

  // Full breakdown view
  return (
    <div className="space-y-4">
      {/* Header with source and composite score */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Database className="w-4 h-4 text-muted-foreground" />
            <span className="text-sm font-semibold text-foreground">Performance Data</span>
          </div>
          <div className="flex items-center gap-2">
            <span className={`px-2 py-1 text-xs font-medium rounded border ${getSourceColor(breakdown.source)}`}>
              {getSourceLabel(breakdown.source)}
            </span>
            {breakdown.level && (
              <span className="text-xs text-muted-foreground">
                {breakdown.level}
              </span>
            )}
          </div>
        </div>

        {breakdown.composite_percentile !== undefined && (
          <div className="text-right">
            <div className="text-xs text-muted-foreground mb-1">Composite Rank</div>
            <div className={`text-2xl font-bold ${getPercentileColor(breakdown.composite_percentile)}`}>
              {breakdown.composite_percentile.toFixed(0)}<span className="text-sm">%ile</span>
            </div>
          </div>
        )}
      </div>

      {/* Sample size info */}
      {breakdown.sample_size && breakdown.days_covered && (
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          <span>{breakdown.sample_size} pitches</span>
          <span>•</span>
          <span>{breakdown.days_covered} days</span>
        </div>
      )}

      {/* Note if present */}
      {breakdown.note && (
        <div className="p-2 bg-yellow-50 border border-yellow-200 rounded text-xs text-yellow-800">
          <Info className="w-3 h-3 inline mr-1" />
          {breakdown.note}
        </div>
      )}

      {/* Metrics breakdown */}
      {breakdown.metrics && breakdown.percentiles && (
        <div>
          <h5 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-1">
            <TrendingUp className="w-4 h-4" />
            Metric Breakdown
          </h5>
          <div className="space-y-3">
            {Object.entries(breakdown.percentiles)
              .filter(([metric]) => breakdown.metrics?.[metric] !== undefined)
              .map(([metric, percentile]) => {
                const rawValue = breakdown.metrics?.[metric];
                const contribution = breakdown.weighted_contributions?.[metric];

                return (
                  <div key={metric} className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-foreground">
                          {formatMetricName(metric)}
                        </span>
                        {contribution !== undefined && (
                          <TooltipProvider>
                            <Tooltip>
                              <TooltipTrigger>
                                <span className="text-muted-foreground">
                                  ({contribution.toFixed(1)}% weight)
                                </span>
                              </TooltipTrigger>
                              <TooltipContent className="bg-popover border-border">
                                <p className="text-xs text-popover-foreground">
                                  Contribution to composite score
                                </p>
                              </TooltipContent>
                            </Tooltip>
                          </TooltipProvider>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        {rawValue !== undefined && (
                          <span className="text-muted-foreground">
                            {typeof rawValue === 'number' ? rawValue.toFixed(1) : rawValue}
                          </span>
                        )}
                        <span className={`font-semibold min-w-[45px] text-right ${getPercentileColor(percentile)}`}>
                          {percentile.toFixed(0)}%ile
                        </span>
                      </div>
                    </div>
                    {getPercentileBar(percentile)}
                  </div>
                );
              })}
          </div>
        </div>
      )}

      {/* Fallback display for game logs */}
      {breakdown.source === 'game_logs' && breakdown.percentiles && (
        <div className="text-xs text-muted-foreground italic">
          Based on traditional stats (OPS/ERA) - pitch-level data not available
        </div>
      )}

      {/* Insufficient data message */}
      {breakdown.source === 'insufficient_data' && (
        <div className="p-3 bg-gray-50 border border-gray-200 rounded text-xs text-gray-700">
          Limited performance data available. Modifier based on baseline estimate.
        </div>
      )}
    </div>
  );
}
