'use client';

import React from 'react';
import { CompositeRanking } from '@/types/prospect';
import {
  TrendingUp,
  TrendingDown,
  Activity,
  Target,
  BarChart3,
  Info,
  Database,
  Zap,
  Award,
  AlertCircle
} from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

interface ExpandedPlayerRowProps {
  prospect: CompositeRanking;
}

export default function ExpandedPlayerRow({ prospect }: ExpandedPlayerRowProps) {
  const breakdown = prospect.performance_breakdown;
  const isPitcher = prospect.position === 'SP' || prospect.position === 'RP' || prospect.position === 'P';

  // Format percentile (0-100, with 100 being best)
  const formatPercentile = (value: number | undefined | null): string => {
    if (value === undefined || value === null || isNaN(value)) return '--';
    // Ensure it's between 0 and 100
    const percentile = Math.max(0, Math.min(100, Math.round(value)));
    return percentile.toString();
  };

  // Format raw values with appropriate units
  const formatRawValue = (metric: string, value: number | undefined): string => {
    if (value === undefined || value === null || isNaN(value)) return '--';

    const formatMap: Record<string, (v: number) => string> = {
      // Hitter metrics
      'exit_velo_90th': (v) => `${v.toFixed(1)} mph`,
      'hard_hit_rate': (v) => `${v.toFixed(1)}%`,
      'contact_rate': (v) => `${v.toFixed(1)}%`,
      'whiff_rate': (v) => `${v.toFixed(1)}%`,
      'chase_rate': (v) => `${v.toFixed(1)}%`,
      // Pitcher metrics
      'zone_rate': (v) => `${v.toFixed(1)}%`,
      'avg_fb_velo': (v) => `${v.toFixed(1)} mph`,
      'hard_contact_rate': (v) => `${v.toFixed(1)}%`,
      // Game log metrics
      'ops': (v) => v.toFixed(3),
      'k_minus_bb': (v) => `${v.toFixed(1)}%`,
      'era': (v) => v.toFixed(2)
    };

    const formatter = formatMap[metric];
    return formatter ? formatter(value) : value.toFixed(1);
  };

  // Get metric display name
  const getMetricDisplayName = (metric: string): string => {
    const names: Record<string, string> = {
      'exit_velo_90th': '90th %ile Exit Velocity',
      'hard_hit_rate': 'Hard Hit Rate',
      'contact_rate': 'Contact Rate',
      'whiff_rate': 'Whiff Rate',
      'chase_rate': 'Chase Rate',
      'zone_rate': 'Zone Rate',
      'avg_fb_velo': 'Fastball Velocity',
      'hard_contact_rate': 'Hard Contact Allowed',
      'ops': 'OPS',
      'k_minus_bb': 'K% - BB%',
      'era': 'ERA'
    };
    return names[metric] || metric.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  };

  // Get percentile color and label
  const getPercentileStyle = (percentile: number | undefined | null) => {
    if (!percentile || isNaN(percentile)) {
      return {
        color: 'text-gray-400',
        bg: 'bg-gray-100',
        barColor: 'bg-gray-300',
        label: 'No Data'
      };
    }

    const p = Math.round(percentile);
    if (p >= 90) return {
      color: 'text-emerald-600',
      bg: 'bg-emerald-50',
      barColor: 'bg-gradient-to-r from-emerald-400 to-green-500',
      label: 'Elite'
    };
    if (p >= 70) return {
      color: 'text-green-600',
      bg: 'bg-green-50',
      barColor: 'bg-gradient-to-r from-green-400 to-green-500',
      label: 'Plus'
    };
    if (p >= 50) return {
      color: 'text-blue-600',
      bg: 'bg-blue-50',
      barColor: 'bg-gradient-to-r from-blue-400 to-blue-500',
      label: 'Above Avg'
    };
    if (p >= 30) return {
      color: 'text-gray-600',
      bg: 'bg-gray-100',
      barColor: 'bg-gray-400',
      label: 'Average'
    };
    if (p >= 10) return {
      color: 'text-orange-600',
      bg: 'bg-orange-50',
      barColor: 'bg-gradient-to-r from-orange-400 to-orange-500',
      label: 'Below Avg'
    };
    return {
      color: 'text-red-600',
      bg: 'bg-red-50',
      barColor: 'bg-gradient-to-r from-red-400 to-red-500',
      label: 'Poor'
    };
  };

  // Create percentile bar visualization
  const PercentileBar = ({ percentile }: { percentile: number | undefined | null }) => {
    const width = percentile && !isNaN(percentile)
      ? Math.max(0, Math.min(100, percentile))
      : 0;
    const style = getPercentileStyle(percentile);

    return (
      <div className="relative w-full">
        {/* Background track */}
        <div className="w-full h-2.5 bg-gray-200 rounded-full overflow-hidden">
          {/* Filled bar */}
          <div
            className={`h-full ${style.barColor} transition-all duration-500 ease-out relative`}
            style={{ width: `${width}%` }}
          >
            {/* Shine effect */}
            <div className="absolute inset-0 bg-gradient-to-t from-transparent via-white/20 to-transparent" />
          </div>
        </div>
        {/* Quartile markers */}
        <div className="absolute inset-0 flex">
          <div className="w-1/4 border-r border-gray-300/50" />
          <div className="w-1/4 border-r border-gray-400/50" />
          <div className="w-1/4 border-r border-gray-400/50" />
          <div className="w-1/4" />
        </div>
      </div>
    );
  };

  // Get data source badge
  const getDataSourceBadge = () => {
    if (!breakdown) return null;

    const badges = {
      'pitch_data': {
        icon: <Database className="w-3 h-3" />,
        label: 'Pitch Data',
        color: 'bg-emerald-100 text-emerald-800 border-emerald-200',
        detail: breakdown.sample_size ? `${breakdown.sample_size.toLocaleString()} pitches` : ''
      },
      'game_logs': {
        icon: <Activity className="w-3 h-3" />,
        label: 'Game Logs',
        color: 'bg-blue-100 text-blue-800 border-blue-200',
        detail: breakdown.days_covered ? `${breakdown.days_covered} days` : ''
      },
      'insufficient_data': {
        icon: <AlertCircle className="w-3 h-3" />,
        label: 'Limited Data',
        color: 'bg-yellow-100 text-yellow-800 border-yellow-200',
        detail: 'Baseline estimate'
      },
      'no_data': {
        icon: null,
        label: 'No Data',
        color: 'bg-gray-100 text-gray-600 border-gray-200',
        detail: ''
      }
    };

    const badge = badges[breakdown.source] || badges['no_data'];

    return (
      <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border ${badge.color}`}>
        {badge.icon}
        <span>{badge.label}</span>
        {badge.detail && <span className="opacity-75">• {badge.detail}</span>}
      </div>
    );
  };

  return (
    <tr className="bg-gradient-to-br from-gray-50/50 to-gray-100/30">
      <td colSpan={13} className="p-0">
        <div className="p-6">
          {/* Modern card-like container */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
            {/* Header with gradient accent */}
            <div className="bg-gradient-to-r from-wine-cyan/10 via-wine-periwinkle/10 to-wine-rose/10 p-4 border-b border-gray-200">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-white rounded-lg shadow-sm">
                    <BarChart3 className="w-5 h-5 text-wine-periwinkle" />
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-gray-900">Performance Analysis</h3>
                    <p className="text-sm text-gray-600">Detailed metrics and scoring breakdown</p>
                  </div>
                </div>
                {getDataSourceBadge()}
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 p-6">
              {/* Left Column: Score Breakdown */}
              <div className="space-y-6">
                {/* Score Components */}
                <div className="bg-gradient-to-br from-gray-50 to-gray-100/50 rounded-xl p-4">
                  <div className="flex items-center gap-2 mb-4">
                    <Target className="w-4 h-4 text-wine-periwinkle" />
                    <h4 className="text-sm font-bold text-gray-900">Score Components</h4>
                  </div>

                  <div className="space-y-3">
                    {/* Base FV */}
                    <div className="bg-white rounded-lg p-3 border border-gray-200">
                      <div className="flex justify-between items-center">
                        <div className="flex items-center gap-2">
                          <div className="w-2 h-2 rounded-full bg-wine-rose" />
                          <span className="text-sm text-gray-600">Base FV (FanGraphs)</span>
                        </div>
                        <span className="text-lg font-bold text-gray-900">{prospect.base_fv.toFixed(1)}</span>
                      </div>
                    </div>

                    {/* Adjustments */}
                    {[
                      { label: 'Performance', value: prospect.performance_modifier, icon: <Activity className="w-3 h-3" /> },
                      { label: 'Trend (30-day)', value: prospect.trend_adjustment, icon: <TrendingUp className="w-3 h-3" /> },
                      { label: 'Age vs Level', value: prospect.age_adjustment, icon: <Award className="w-3 h-3" /> }
                    ].map((item) => (
                      <div key={item.label} className="bg-white rounded-lg p-3 border border-gray-200">
                        <div className="flex justify-between items-center">
                          <div className="flex items-center gap-2">
                            <div className="text-gray-400">{item.icon}</div>
                            <span className="text-sm text-gray-600">{item.label}</span>
                          </div>
                          <span className={`text-lg font-bold ${item.value >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                            {item.value >= 0 ? '+' : ''}{item.value.toFixed(1)}
                          </span>
                        </div>
                      </div>
                    ))}

                    {/* Final Score */}
                    <div className="bg-gradient-to-r from-wine-periwinkle/10 to-wine-cyan/10 rounded-lg p-3 border border-wine-periwinkle/30">
                      <div className="flex justify-between items-center">
                        <div className="flex items-center gap-2">
                          <Zap className="w-4 h-4 text-wine-periwinkle" />
                          <span className="text-sm font-bold text-gray-900">Composite Score</span>
                        </div>
                        <span className="text-xl font-black text-wine-periwinkle">
                          {prospect.composite_score.toFixed(1)}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Insights */}
                <div className="bg-gradient-to-br from-amber-50 to-yellow-50 rounded-xl p-4 border border-amber-200">
                  <div className="flex items-center gap-2 mb-3">
                    <Info className="w-4 h-4 text-amber-600" />
                    <h4 className="text-sm font-bold text-gray-900">Key Insights</h4>
                  </div>
                  <div className="space-y-2">
                    {prospect.performance_modifier > 5 && (
                      <div className="flex items-start gap-2">
                        <div className="w-1.5 h-1.5 rounded-full bg-green-500 mt-1.5" />
                        <span className="text-xs text-gray-700">Significantly outperforming level competition</span>
                      </div>
                    )}
                    {prospect.performance_modifier < -5 && (
                      <div className="flex items-start gap-2">
                        <div className="w-1.5 h-1.5 rounded-full bg-red-500 mt-1.5" />
                        <span className="text-xs text-gray-700">Struggling relative to current level</span>
                      </div>
                    )}
                    {prospect.trend_adjustment >= 2 && (
                      <div className="flex items-start gap-2">
                        <div className="w-1.5 h-1.5 rounded-full bg-green-500 mt-1.5" />
                        <span className="text-xs text-gray-700">On a hot streak - trending upward</span>
                      </div>
                    )}
                    {prospect.trend_adjustment <= -2 && (
                      <div className="flex items-start gap-2">
                        <div className="w-1.5 h-1.5 rounded-full bg-red-500 mt-1.5" />
                        <span className="text-xs text-gray-700">Recent performance decline detected</span>
                      </div>
                    )}
                    {prospect.age_adjustment > 0 && (
                      <div className="flex items-start gap-2">
                        <div className="w-1.5 h-1.5 rounded-full bg-blue-500 mt-1.5" />
                        <span className="text-xs text-gray-700">Young for level - shows advanced development</span>
                      </div>
                    )}
                    {prospect.age_adjustment < 0 && (
                      <div className="flex items-start gap-2">
                        <div className="w-1.5 h-1.5 rounded-full bg-orange-500 mt-1.5" />
                        <span className="text-xs text-gray-700">Old for level - organizational depth player</span>
                      </div>
                    )}
                    {Math.abs(prospect.total_adjustment) < 1 && (
                      <div className="flex items-start gap-2">
                        <div className="w-1.5 h-1.5 rounded-full bg-gray-500 mt-1.5" />
                        <span className="text-xs text-gray-700">Performing as expected based on scouting grades</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Right Column: Metrics Breakdown */}
              <div className="space-y-6">
                {breakdown && breakdown.percentiles && Object.keys(breakdown.percentiles).length > 0 ? (
                  <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl p-4">
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center gap-2">
                        <BarChart3 className="w-4 h-4 text-blue-600" />
                        <h4 className="text-sm font-bold text-gray-900">Performance Metrics</h4>
                      </div>
                      {breakdown.composite_percentile !== undefined && !isNaN(breakdown.composite_percentile) && (
                        <TooltipProvider>
                          <Tooltip>
                            <TooltipTrigger>
                              <div className={`px-3 py-1 rounded-full text-xs font-bold ${getPercentileStyle(breakdown.composite_percentile).bg} ${getPercentileStyle(breakdown.composite_percentile).color}`}>
                                {formatPercentile(breakdown.composite_percentile)}th %ile Overall
                              </div>
                            </TooltipTrigger>
                            <TooltipContent>
                              <p className="text-sm">Composite performance vs level peers</p>
                            </TooltipContent>
                          </Tooltip>
                        </TooltipProvider>
                      )}
                    </div>

                    <div className="space-y-4">
                      {Object.entries(breakdown.percentiles)
                        .filter(([_, percentile]) => percentile !== undefined && !isNaN(percentile))
                        .map(([metric, percentile]) => {
                          const rawValue = breakdown.metrics?.[metric];
                          const style = getPercentileStyle(percentile);

                          return (
                            <div key={metric} className="bg-white rounded-lg p-3 border border-gray-200">
                              {/* Metric name and values */}
                              <div className="flex items-center justify-between mb-2">
                                <span className="text-sm font-medium text-gray-900">
                                  {getMetricDisplayName(metric)}
                                </span>
                                <div className="flex items-center gap-3">
                                  {/* Raw value */}
                                  {rawValue !== undefined && (
                                    <span className="text-sm font-medium text-gray-600">
                                      {formatRawValue(metric, rawValue)}
                                    </span>
                                  )}
                                  {/* Percentile */}
                                  <TooltipProvider>
                                    <Tooltip>
                                      <TooltipTrigger>
                                        <div className={`px-2 py-0.5 rounded text-xs font-bold ${style.bg} ${style.color}`}>
                                          {formatPercentile(percentile)}th
                                        </div>
                                      </TooltipTrigger>
                                      <TooltipContent>
                                        <p className="text-xs">{style.label} ({formatPercentile(percentile)}th percentile)</p>
                                      </TooltipContent>
                                    </Tooltip>
                                  </TooltipProvider>
                                </div>
                              </div>
                              {/* Percentile bar */}
                              <PercentileBar percentile={percentile} />
                            </div>
                          );
                        })}
                    </div>

                    {/* Data quality note */}
                    {breakdown.note && (
                      <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                        <div className="flex items-start gap-2">
                          <AlertCircle className="w-4 h-4 text-yellow-600 mt-0.5" />
                          <p className="text-xs text-yellow-800">{breakdown.note}</p>
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="bg-gray-50 rounded-xl p-6 text-center">
                    <Database className="w-8 h-8 text-gray-400 mx-auto mb-2" />
                    <p className="text-sm text-gray-600">No performance metrics available</p>
                    <p className="text-xs text-gray-500 mt-1">Performance data will appear when available</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </td>
    </tr>
  );
}