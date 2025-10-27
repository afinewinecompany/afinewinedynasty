'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { ChevronDown, ChevronUp, TrendingUp, TrendingDown, Minus, AlertCircle, Database, Activity } from 'lucide-react';
import { CompositeRanking } from '@/types/prospect';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

interface CompositeRankingsCardImprovedProps {
  prospect: CompositeRanking;
  viewMode?: 'card' | 'compact';
}

export default function CompositeRankingsCardImproved({
  prospect,
  viewMode = 'card'
}: CompositeRankingsCardImprovedProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Helper functions for formatting
  const formatPercentile = (value: number | undefined | null): string => {
    if (value === undefined || value === null || isNaN(value)) {
      return '--';
    }
    return `${Math.round(value)}`;
  };

  const getPercentileStyle = (percentile: number | undefined | null) => {
    if (!percentile || isNaN(percentile)) {
      return { color: 'text-gray-400', bg: 'bg-gray-50', label: 'No Data' };
    }
    if (percentile >= 90) return { color: 'text-emerald-700', bg: 'bg-gradient-to-r from-emerald-50 to-green-50', label: 'Elite' };
    if (percentile >= 75) return { color: 'text-green-600', bg: 'bg-green-50', label: 'Plus' };
    if (percentile >= 60) return { color: 'text-blue-600', bg: 'bg-blue-50', label: 'Above Avg' };
    if (percentile >= 40) return { color: 'text-gray-600', bg: 'bg-gray-50', label: 'Average' };
    if (percentile >= 25) return { color: 'text-orange-600', bg: 'bg-orange-50', label: 'Below Avg' };
    return { color: 'text-red-600', bg: 'bg-red-50', label: 'Poor' };
  };

  const getPercentileBar = (percentile: number | undefined | null) => {
    const width = percentile && !isNaN(percentile) ? Math.max(0, Math.min(100, percentile)) : 0;
    let barColor = 'bg-gray-300';

    if (percentile && !isNaN(percentile)) {
      if (percentile >= 75) barColor = 'bg-gradient-to-r from-green-500 to-emerald-500';
      else if (percentile >= 50) barColor = 'bg-gradient-to-r from-blue-500 to-sky-500';
      else if (percentile >= 25) barColor = 'bg-gradient-to-r from-yellow-500 to-orange-500';
      else barColor = 'bg-gradient-to-r from-red-500 to-rose-500';
    }

    return (
      <div className="relative w-full h-2 bg-gray-200 rounded-full overflow-hidden">
        <div
          className={`absolute left-0 top-0 h-full ${barColor} transition-all duration-500 ease-out`}
          style={{ width: `${width}%` }}
        />
        {/* Markers at 25%, 50%, 75% */}
        <div className="absolute left-1/4 top-0 w-px h-full bg-gray-400 opacity-30" />
        <div className="absolute left-1/2 top-0 w-px h-full bg-gray-400 opacity-30" />
        <div className="absolute left-3/4 top-0 w-px h-full bg-gray-400 opacity-30" />
      </div>
    );
  };

  const getTrendIcon = (trend: number) => {
    if (trend >= 2) return <TrendingUp className="w-4 h-4 text-green-500" />;
    if (trend <= -2) return <TrendingDown className="w-4 h-4 text-red-500" />;
    return <Minus className="w-4 h-4 text-gray-400" />;
  };

  const getTrendLabel = (trend: number) => {
    if (trend >= 5) return 'Hot';
    if (trend >= 2) return 'Surging';
    if (trend <= -5) return 'Cold';
    if (trend <= -2) return 'Cooling';
    return 'Stable';
  };

  const getTierStyle = (tier: number | null) => {
    switch (tier) {
      case 1:
        return 'bg-gradient-to-r from-yellow-400 via-yellow-500 to-amber-600 text-white shadow-lg';
      case 2:
        return 'bg-gradient-to-r from-blue-500 to-blue-600 text-white';
      case 3:
        return 'bg-gradient-to-r from-green-500 to-green-600 text-white';
      case 4:
        return 'bg-gray-600 text-white';
      case 5:
        return 'bg-gray-400 text-white';
      default:
        return 'bg-gray-300 text-gray-700';
    }
  };

  const getToolGradeStyle = (grade: number | null | undefined) => {
    if (!grade) return { color: 'text-gray-400', label: '--' };
    if (grade >= 70) return { color: 'text-yellow-600 font-bold', label: grade.toString() };
    if (grade >= 60) return { color: 'text-blue-600 font-semibold', label: grade.toString() };
    if (grade >= 50) return { color: 'text-green-600 font-medium', label: grade.toString() };
    return { color: 'text-gray-600', label: grade.toString() };
  };

  const getDataSourceInfo = () => {
    const breakdown = prospect.performance_breakdown;
    if (!breakdown) return { label: 'No Data', color: 'bg-gray-100 text-gray-600', icon: null };

    switch (breakdown.source) {
      case 'pitch_data':
        return {
          label: `Pitch Data (${breakdown.sample_size?.toLocaleString() || 0} pitches)`,
          color: 'bg-gradient-to-r from-green-50 to-emerald-50 text-green-800 border border-green-200',
          icon: <Database className="w-3 h-3" />
        };
      case 'game_logs':
        return {
          label: 'Game Logs',
          color: 'bg-gradient-to-r from-blue-50 to-sky-50 text-blue-800 border border-blue-200',
          icon: <Activity className="w-3 h-3" />
        };
      case 'insufficient_data':
        return {
          label: 'Limited Data',
          color: 'bg-gradient-to-r from-yellow-50 to-amber-50 text-yellow-800 border border-yellow-200',
          icon: <AlertCircle className="w-3 h-3" />
        };
      default:
        return {
          label: 'No Data',
          color: 'bg-gray-100 text-gray-600 border border-gray-200',
          icon: null
        };
    }
  };

  const isPitcher = prospect.position === 'SP' || prospect.position === 'RP' || prospect.position === 'P';
  const dataSource = getDataSourceInfo();
  const breakdown = prospect.performance_breakdown;

  // Get key metrics for display
  const getKeyMetrics = () => {
    if (!breakdown?.percentiles) return [];

    const metrics = [];
    if (isPitcher) {
      if (breakdown.percentiles.avg_fb_velo !== undefined) {
        metrics.push({ name: 'Velocity', value: breakdown.percentiles.avg_fb_velo, raw: breakdown.metrics?.avg_fb_velo });
      }
      if (breakdown.percentiles.zone_rate !== undefined) {
        metrics.push({ name: 'Zone Rate', value: breakdown.percentiles.zone_rate, raw: breakdown.metrics?.zone_rate });
      }
      if (breakdown.percentiles.hard_contact_rate !== undefined) {
        metrics.push({ name: 'Hard Contact', value: breakdown.percentiles.hard_contact_rate, raw: breakdown.metrics?.hard_contact_rate });
      }
    } else {
      if (breakdown.percentiles.exit_velo_90th !== undefined) {
        metrics.push({ name: 'Exit Velo', value: breakdown.percentiles.exit_velo_90th, raw: breakdown.metrics?.exit_velo_90th });
      }
      if (breakdown.percentiles.hard_hit_rate !== undefined) {
        metrics.push({ name: 'Hard Hit', value: breakdown.percentiles.hard_hit_rate, raw: breakdown.metrics?.hard_hit_rate });
      }
      if (breakdown.percentiles.whiff_rate !== undefined) {
        metrics.push({ name: 'Whiff Rate', value: breakdown.percentiles.whiff_rate, raw: breakdown.metrics?.whiff_rate });
      }
    }
    return metrics.slice(0, 3); // Return top 3 metrics
  };

  const keyMetrics = getKeyMetrics();

  return (
    <div className="relative rounded-xl border border-gray-200 bg-white hover:shadow-lg transition-all duration-300 overflow-hidden">
      {/* Tier Badge - Floating */}
      {prospect.tier && prospect.tier_label && (
        <div className="absolute top-3 right-3 z-10">
          <span className={`px-3 py-1 text-xs font-bold rounded-full ${getTierStyle(prospect.tier)}`}>
            {prospect.tier_label}
          </span>
        </div>
      )}

      <div className="p-4">
        {/* Header Section */}
        <div className="flex items-start gap-3 mb-4">
          {/* Rank Badge */}
          <div className="flex-shrink-0">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-gradient-to-br from-wine-cyan to-wine-periwinkle text-white font-bold text-lg shadow-md">
              #{prospect.rank}
            </div>
          </div>

          {/* Name and Info */}
          <div className="flex-1 min-w-0">
            <Link
              href={`/prospects/${prospect.prospect_id}`}
              className="text-lg font-bold text-gray-900 hover:text-wine-rose transition-colors block truncate"
            >
              {prospect.name}
            </Link>
            <div className="flex flex-wrap items-center gap-2 mt-1">
              <span className="px-2 py-0.5 bg-gradient-to-r from-gray-100 to-gray-50 rounded text-xs font-semibold text-gray-700">
                {prospect.position}
              </span>
              <span className="text-sm text-gray-600">{prospect.organization || 'FA'}</span>
              <span className="text-sm text-gray-500">•</span>
              <span className="text-sm text-gray-500">{prospect.level || '--'}</span>
              <span className="text-sm text-gray-500">•</span>
              <span className="text-sm text-gray-500">Age {prospect.age || '--'}</span>
            </div>
          </div>
        </div>

        {/* Score Cards */}
        <div className="grid grid-cols-3 gap-2 mb-4">
          <div className="bg-gradient-to-br from-pink-50 to-rose-50 rounded-lg p-3 text-center">
            <div className="text-xs text-gray-600 mb-1">Base FV</div>
            <div className="text-2xl font-bold text-wine-rose">
              {prospect.base_fv.toFixed(0)}
            </div>
          </div>
          <div className="bg-gradient-to-br from-purple-50 to-indigo-50 rounded-lg p-3 text-center">
            <div className="text-xs text-gray-600 mb-1">Composite</div>
            <div className="text-2xl font-black text-wine-periwinkle">
              {prospect.composite_score.toFixed(1)}
            </div>
          </div>
          <div className={`rounded-lg p-3 text-center ${prospect.total_adjustment >= 0 ? 'bg-gradient-to-br from-green-50 to-emerald-50' : 'bg-gradient-to-br from-red-50 to-rose-50'}`}>
            <div className="text-xs text-gray-600 mb-1">Adjustment</div>
            <div className={`text-2xl font-bold ${prospect.total_adjustment >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {prospect.total_adjustment >= 0 ? '+' : ''}{prospect.total_adjustment.toFixed(1)}
            </div>
          </div>
        </div>

        {/* Data Source & Overall Percentile */}
        <div className="mb-4 p-3 bg-gradient-to-r from-gray-50 to-gray-100 rounded-lg">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              {dataSource.icon}
              <span className={`px-2 py-1 text-xs font-medium rounded-full ${dataSource.color}`}>
                {dataSource.label}
              </span>
            </div>
            {breakdown?.composite_percentile !== undefined && !isNaN(breakdown.composite_percentile) && (
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger>
                    <div className={`text-right ${getPercentileStyle(breakdown.composite_percentile).color}`}>
                      <div className="text-xs text-gray-500">Overall Performance</div>
                      <div className="text-2xl font-bold">
                        {formatPercentile(breakdown.composite_percentile)}
                        <span className="text-sm">%ile</span>
                      </div>
                    </div>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p className="text-sm">Performance vs level peers</p>
                    <p className="text-xs text-gray-500">{getPercentileStyle(breakdown.composite_percentile).label}</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )}
          </div>

          {/* Key Metrics Preview */}
          {keyMetrics.length > 0 && (
            <div className="space-y-2 mt-3">
              {keyMetrics.map((metric, idx) => (
                <div key={idx} className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium text-gray-700">{metric.name}</span>
                    <div className="flex items-center gap-2">
                      {metric.raw !== undefined && (
                        <span className="text-gray-500">
                          {typeof metric.raw === 'number' ? metric.raw.toFixed(1) : metric.raw}
                        </span>
                      )}
                      <span className={`font-bold ${getPercentileStyle(metric.value).color}`}>
                        {formatPercentile(metric.value)}%ile
                      </span>
                    </div>
                  </div>
                  {getPercentileBar(metric.value)}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Trend & Tool Grades */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            {getTrendIcon(prospect.trend_adjustment)}
            <span className="text-sm font-medium text-gray-700">
              {getTrendLabel(prospect.trend_adjustment)}
            </span>
          </div>

          {/* Tool Grades Summary */}
          <div className="flex flex-wrap gap-1 justify-end max-w-[60%]">
            {isPitcher ? (
              <>
                {prospect.tool_grades.fastball && (
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger>
                        <span className={`text-xs px-1.5 py-0.5 rounded ${getToolGradeStyle(prospect.tool_grades.fastball).color}`}>
                          FB:{getToolGradeStyle(prospect.tool_grades.fastball).label}
                        </span>
                      </TooltipTrigger>
                      <TooltipContent>
                        <p className="text-xs">Fastball Grade</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                )}
                {prospect.tool_grades.slider && (
                  <span className={`text-xs px-1.5 py-0.5 rounded ${getToolGradeStyle(prospect.tool_grades.slider).color}`}>
                    SL:{getToolGradeStyle(prospect.tool_grades.slider).label}
                  </span>
                )}
                {prospect.tool_grades.command && (
                  <span className={`text-xs px-1.5 py-0.5 rounded ${getToolGradeStyle(prospect.tool_grades.command).color}`}>
                    CMD:{getToolGradeStyle(prospect.tool_grades.command).label}
                  </span>
                )}
              </>
            ) : (
              <>
                {prospect.tool_grades.hit && (
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger>
                        <span className={`text-xs px-1.5 py-0.5 rounded ${getToolGradeStyle(prospect.tool_grades.hit).color}`}>
                          Hit:{getToolGradeStyle(prospect.tool_grades.hit).label}
                        </span>
                      </TooltipTrigger>
                      <TooltipContent>
                        <p className="text-xs">Hit Tool Grade</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                )}
                {prospect.tool_grades.power && (
                  <span className={`text-xs px-1.5 py-0.5 rounded ${getToolGradeStyle(prospect.tool_grades.power).color}`}>
                    Pwr:{getToolGradeStyle(prospect.tool_grades.power).label}
                  </span>
                )}
                {prospect.tool_grades.speed && (
                  <span className={`text-xs px-1.5 py-0.5 rounded ${getToolGradeStyle(prospect.tool_grades.speed).color}`}>
                    Spd:{getToolGradeStyle(prospect.tool_grades.speed).label}
                  </span>
                )}
              </>
            )}
          </div>
        </div>

        {/* Expand/Collapse Button */}
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="w-full pt-3 border-t border-gray-200 flex items-center justify-center gap-1 text-sm text-gray-600 hover:text-gray-900 transition-colors group"
        >
          <span>{isExpanded ? 'Hide' : 'Show'} Detailed Analysis</span>
          {isExpanded ? (
            <ChevronUp className="w-4 h-4 group-hover:translate-y-[-2px] transition-transform" />
          ) : (
            <ChevronDown className="w-4 h-4 group-hover:translate-y-[2px] transition-transform" />
          )}
        </button>

        {/* Expanded Details */}
        {isExpanded && (
          <div className="mt-4 space-y-4 animate-in fade-in slide-in-from-top-2 duration-300">
            {/* Score Breakdown */}
            <div className="p-3 bg-gradient-to-r from-gray-50 to-gray-100 rounded-lg">
              <h4 className="text-sm font-bold text-gray-900 mb-3">Score Breakdown</h4>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between items-center">
                  <span className="text-gray-600">Base FV (FanGraphs)</span>
                  <span className="font-semibold">{prospect.base_fv.toFixed(1)}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-600">Performance</span>
                  <span className={`font-semibold ${prospect.performance_modifier >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {prospect.performance_modifier >= 0 ? '+' : ''}{prospect.performance_modifier.toFixed(1)}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-600">Trend (30-day)</span>
                  <span className={`font-semibold ${prospect.trend_adjustment >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {prospect.trend_adjustment >= 0 ? '+' : ''}{prospect.trend_adjustment.toFixed(1)}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-600">Age vs Level</span>
                  <span className={`font-semibold ${prospect.age_adjustment >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {prospect.age_adjustment >= 0 ? '+' : ''}{prospect.age_adjustment.toFixed(1)}
                  </span>
                </div>
                <div className="flex justify-between items-center pt-2 border-t border-gray-300">
                  <span className="font-bold text-gray-900">Final Score</span>
                  <span className="font-black text-wine-periwinkle text-lg">{prospect.composite_score.toFixed(1)}</span>
                </div>
              </div>
            </div>

            {/* All Metrics Breakdown */}
            {breakdown?.percentiles && Object.keys(breakdown.percentiles).length > 0 && (
              <div className="p-3 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg">
                <h4 className="text-sm font-bold text-gray-900 mb-3">Performance Metrics</h4>
                <div className="space-y-3">
                  {Object.entries(breakdown.percentiles)
                    .filter(([_, value]) => value !== undefined && !isNaN(value))
                    .map(([metric, percentile]) => {
                      const rawValue = breakdown.metrics?.[metric];
                      const metricName = metric.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

                      return (
                        <div key={metric} className="space-y-1">
                          <div className="flex items-center justify-between text-xs">
                            <span className="font-medium text-gray-700 capitalize">
                              {metricName}
                            </span>
                            <div className="flex items-center gap-2">
                              {rawValue !== undefined && (
                                <span className="text-gray-500">
                                  {typeof rawValue === 'number' ? rawValue.toFixed(1) : rawValue}
                                </span>
                              )}
                              <span className={`font-bold min-w-[50px] text-right ${getPercentileStyle(percentile).color}`}>
                                {formatPercentile(percentile)}%ile
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

            {/* Context & Insights */}
            <div className="p-3 bg-gradient-to-r from-amber-50 to-yellow-50 rounded-lg">
              <h4 className="text-sm font-bold text-gray-900 mb-2">Key Insights</h4>
              <div className="space-y-1.5 text-xs">
                {prospect.performance_modifier > 5 && (
                  <div className="flex items-start gap-1.5">
                    <span className="text-green-600 mt-0.5">●</span>
                    <span className="text-gray-700">Significantly outperforming peers at current level</span>
                  </div>
                )}
                {prospect.performance_modifier < -5 && (
                  <div className="flex items-start gap-1.5">
                    <span className="text-red-600 mt-0.5">●</span>
                    <span className="text-gray-700">Struggling relative to level competition</span>
                  </div>
                )}
                {prospect.trend_adjustment >= 2 && (
                  <div className="flex items-start gap-1.5">
                    <span className="text-green-600 mt-0.5">●</span>
                    <span className="text-gray-700">On a hot streak - trending upward</span>
                  </div>
                )}
                {prospect.trend_adjustment <= -2 && (
                  <div className="flex items-start gap-1.5">
                    <span className="text-red-600 mt-0.5">●</span>
                    <span className="text-gray-700">Recent performance decline detected</span>
                  </div>
                )}
                {prospect.age_adjustment > 0 && (
                  <div className="flex items-start gap-1.5">
                    <span className="text-blue-600 mt-0.5">●</span>
                    <span className="text-gray-700">Young for level - shows advanced development</span>
                  </div>
                )}
                {prospect.age_adjustment < 0 && (
                  <div className="flex items-start gap-1.5">
                    <span className="text-orange-600 mt-0.5">●</span>
                    <span className="text-gray-700">Old for level - may be organizational depth</span>
                  </div>
                )}
                {Math.abs(prospect.total_adjustment) < 1 && (
                  <div className="flex items-start gap-1.5">
                    <span className="text-gray-600 mt-0.5">●</span>
                    <span className="text-gray-700">Performing as expected based on scouting grades</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}