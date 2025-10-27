'use client';

import React from 'react';
import { CompositeRanking } from '@/types/prospect';
import { useProspectPercentiles } from '@/contexts/PercentilesContext';
import {
  calculateCompositePercentile,
  formatMetricName,
  formatMetricValue,
  getPercentileInfo,
} from '@/utils/calculatePercentiles';
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
  AlertCircle,
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

const ExpandedPlayerRowV2 = ({ prospect }: ExpandedPlayerRowProps) => {
  const percentiles = useProspectPercentiles(prospect.prospect_id);
  const breakdown = prospect.performance_breakdown;
  const isPitcher = ['SP', 'RP', 'P'].includes(prospect.position);

  // Calculate composite percentile from individual metric percentiles
  const compositePercentile = breakdown?.metrics
    ? calculateCompositePercentile(breakdown.metrics, percentiles, prospect.position)
    : 0;

  // Get key metrics based on position
  const getKeyMetrics = () => {
    if (!breakdown?.metrics) return [];

    const metrics = isPitcher
      ? ['avg_fb_velo', 'whiff_rate', 'zone_rate', 'k_minus_bb', 'hard_contact_rate']
      : ['exit_velo_90th', 'hard_hit_rate', 'contact_rate', 'whiff_rate', 'chase_rate'];

    return metrics
      .filter(m => breakdown.metrics[m] !== undefined)
      .map(metric => ({
        name: metric,
        value: breakdown.metrics[metric],
        percentile: percentiles[metric] || 0,
      }))
      .sort((a, b) => b.percentile - a.percentile); // Sort by percentile, best first
  };

  const keyMetrics = getKeyMetrics();

  // Percentile bar component
  const PercentileBar = ({ percentile }: { percentile: number }) => {
    const info = getPercentileInfo(percentile);

    return (
      <div className="relative w-full">
        {/* Background track */}
        <div className="w-full h-3 bg-gray-200 rounded-full overflow-hidden">
          {/* Filled bar */}
          <div
            className={`h-full ${info.barColor} transition-all duration-500 ease-out relative`}
            style={{ width: `${percentile}%` }}
          >
            {/* Shine effect */}
            <div className="absolute inset-0 bg-gradient-to-t from-transparent via-white/20 to-transparent" />
          </div>
        </div>
        {/* Quartile markers */}
        <div className="absolute inset-0 flex pointer-events-none">
          <div className="w-1/4 border-r border-gray-300/50" />
          <div className="w-1/4 border-r border-gray-400/50" />
          <div className="w-1/4 border-r border-gray-400/50" />
          <div className="w-1/4" />
        </div>
        {/* Labels */}
        <div className="flex justify-between mt-1 text-[10px] text-gray-500">
          <span>0</span>
          <span>25</span>
          <span>50</span>
          <span>75</span>
          <span>100</span>
        </div>
      </div>
    );
  };

  // Data source badge
  const getDataSourceBadge = () => {
    if (!breakdown) return { label: 'No Data', color: 'bg-gray-100 text-gray-600', icon: null };

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
        detail: ''
      },
      'insufficient_data': {
        icon: <AlertCircle className="w-3 h-3" />,
        label: 'Limited Data',
        color: 'bg-yellow-100 text-yellow-800 border-yellow-200',
        detail: ''
      },
      'no_data': {
        icon: null,
        label: 'No Data',
        color: 'bg-gray-100 text-gray-600 border-gray-200',
        detail: ''
      }
    };

    const badge = badges[breakdown.source] || badges['no_data'];
    return badge;
  };

  const dataSource = getDataSourceBadge();

  return (
    <tr className="bg-gradient-to-br from-gray-50/50 to-gray-100/30">
      <td colSpan={13} className="p-0">
        <div className="p-6">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
            {/* Header */}
            <div className="bg-gradient-to-r from-wine-cyan/10 via-wine-periwinkle/10 to-wine-rose/10 p-4 border-b border-gray-200">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-white rounded-lg shadow-sm">
                    <BarChart3 className="w-5 h-5 text-wine-periwinkle" />
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-gray-900">Performance Analysis</h3>
                    <p className="text-sm text-gray-600">
                      Percentile rankings compared to all {isPitcher ? 'pitchers' : 'hitters'}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border ${dataSource.color}`}>
                    {dataSource.icon}
                    <span>{dataSource.label}</span>
                    {dataSource.detail && <span className="opacity-75">• {dataSource.detail}</span>}
                  </div>
                  {compositePercentile > 0 && (
                    <div className={`px-3 py-1 rounded-full text-xs font-bold ${getPercentileInfo(compositePercentile).bgColor} ${getPercentileInfo(compositePercentile).color} border ${getPercentileInfo(compositePercentile).borderColor}`}>
                      {compositePercentile}th %ile Overall
                    </div>
                  )}
                </div>
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

                {/* Top 3 Metrics */}
                {keyMetrics.length > 0 && (
                  <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl p-4">
                    <div className="flex items-center gap-2 mb-4">
                      <TrendingUp className="w-4 h-4 text-blue-600" />
                      <h4 className="text-sm font-bold text-gray-900">Top Performance Metrics</h4>
                    </div>
                    <div className="space-y-3">
                      {keyMetrics.slice(0, 3).map((metric) => {
                        const info = getPercentileInfo(metric.percentile);
                        return (
                          <div key={metric.name} className="bg-white rounded-lg p-3 border border-gray-200">
                            <div className="flex justify-between items-center mb-2">
                              <span className="text-sm font-medium text-gray-900">
                                {formatMetricName(metric.name)}
                              </span>
                              <div className="flex items-center gap-2">
                                <span className="text-sm text-gray-600">
                                  {formatMetricValue(metric.name, metric.value)}
                                </span>
                                <div className={`px-2 py-1 rounded text-xs font-bold ${info.bgColor} ${info.color}`}>
                                  {metric.percentile}th %ile
                                </div>
                              </div>
                            </div>
                            <PercentileBar percentile={metric.percentile} />
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>

              {/* Right Column: All Metrics */}
              <div className="space-y-6">
                {breakdown?.metrics && Object.keys(breakdown.metrics).length > 0 ? (
                  <div className="bg-gradient-to-br from-purple-50 to-pink-50 rounded-xl p-4">
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center gap-2">
                        <BarChart3 className="w-4 h-4 text-purple-600" />
                        <h4 className="text-sm font-bold text-gray-900">All Performance Metrics</h4>
                      </div>
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger>
                            <Info className="w-4 h-4 text-gray-400" />
                          </TooltipTrigger>
                          <TooltipContent>
                            <p className="text-xs">Percentiles calculated vs all players at this position</p>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </div>

                    <div className="space-y-3 max-h-96 overflow-y-auto">
                      {Object.entries(breakdown.metrics)
                        .filter(([metric]) => percentiles[metric] !== undefined)
                        .sort((a, b) => (percentiles[b[0]] || 0) - (percentiles[a[0]] || 0))
                        .map(([metric, value]) => {
                          const percentile = percentiles[metric] || 0;
                          const info = getPercentileInfo(percentile);

                          return (
                            <div key={metric} className="bg-white rounded-lg p-3 border border-gray-200">
                              <div className="flex items-center justify-between mb-2">
                                <span className="text-sm font-medium text-gray-900">
                                  {formatMetricName(metric)}
                                </span>
                                <div className="flex items-center gap-3">
                                  <span className="text-sm font-medium text-gray-600">
                                    {formatMetricValue(metric, value)}
                                  </span>
                                  <TooltipProvider>
                                    <Tooltip>
                                      <TooltipTrigger>
                                        <div className={`px-2.5 py-1 rounded text-xs font-bold ${info.bgColor} ${info.color} border ${info.borderColor}`}>
                                          {percentile}th
                                        </div>
                                      </TooltipTrigger>
                                      <TooltipContent>
                                        <div className="text-xs">
                                          <p className="font-semibold">{info.label}</p>
                                          <p>Better than {percentile}% of {isPitcher ? 'pitchers' : 'hitters'}</p>
                                        </div>
                                      </TooltipContent>
                                    </Tooltip>
                                  </TooltipProvider>
                                </div>
                              </div>
                              <PercentileBar percentile={percentile} />
                            </div>
                          );
                        })}
                    </div>

                    {/* Legend */}
                    <div className="mt-4 pt-4 border-t border-gray-200">
                      <div className="grid grid-cols-3 gap-2 text-[10px]">
                        <div className="flex items-center gap-1">
                          <div className="w-3 h-3 bg-gradient-to-r from-emerald-400 to-green-500 rounded" />
                          <span className="text-gray-600">Elite (90+)</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <div className="w-3 h-3 bg-gradient-to-r from-green-400 to-green-500 rounded" />
                          <span className="text-gray-600">Plus (75-89)</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <div className="w-3 h-3 bg-gradient-to-r from-blue-400 to-blue-500 rounded" />
                          <span className="text-gray-600">Above (60-74)</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <div className="w-3 h-3 bg-gray-400 rounded" />
                          <span className="text-gray-600">Average (40-59)</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <div className="w-3 h-3 bg-gradient-to-r from-orange-400 to-orange-500 rounded" />
                          <span className="text-gray-600">Below (25-39)</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <div className="w-3 h-3 bg-gradient-to-r from-red-400 to-red-500 rounded" />
                          <span className="text-gray-600">Poor (<25)</span>
                        </div>
                      </div>
                    </div>
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
};

export default ExpandedPlayerRowV2;