'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import {
  ChevronDown,
  ChevronUp,
  TrendingUp,
  TrendingDown,
  Minus,
  Activity,
  Target,
  Zap,
  Award,
  BarChart3,
  Info
} from 'lucide-react';
import { CompositeRanking } from '@/types/prospect';
import PerformanceBreakdown from './PerformanceBreakdown';

interface CompositeRankingsCardProps {
  prospect: CompositeRanking;
}

export default function CompositeRankingsCardV2({ prospect }: CompositeRankingsCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const isPitcher = prospect.position === 'SP' || prospect.position === 'RP' || prospect.position === 'P';

  // Enhanced tier styling with gradients
  const getTierStyle = (tier: number | null) => {
    switch (tier) {
      case 1:
        return {
          bg: 'bg-gradient-to-r from-yellow-400 via-yellow-500 to-amber-600',
          text: 'text-white',
          label: 'Elite',
          icon: '⭐'
        };
      case 2:
        return {
          bg: 'bg-gradient-to-r from-blue-500 to-blue-700',
          text: 'text-white',
          label: prospect.tier_label || 'Plus',
          icon: '🔥'
        };
      case 3:
        return {
          bg: 'bg-gradient-to-r from-green-500 to-green-700',
          text: 'text-white',
          label: prospect.tier_label || 'Above Average',
          icon: '✨'
        };
      case 4:
        return {
          bg: 'bg-gradient-to-r from-gray-500 to-gray-700',
          text: 'text-white',
          label: prospect.tier_label || 'Average',
          icon: ''
        };
      case 5:
        return {
          bg: 'bg-gray-400',
          text: 'text-white',
          label: prospect.tier_label || 'Below Average',
          icon: ''
        };
      default:
        return {
          bg: 'bg-gray-300',
          text: 'text-gray-700',
          label: 'Unranked',
          icon: ''
        };
    }
  };

  const getTrendIndicator = (trend: number) => {
    if (trend >= 5) {
      return { icon: <TrendingUp className="w-5 h-5" />, color: 'text-red-500', label: '🔥 Hot' };
    } else if (trend >= 2) {
      return { icon: <TrendingUp className="w-4 h-4" />, color: 'text-green-500', label: 'Rising' };
    } else if (trend <= -5) {
      return { icon: <TrendingDown className="w-5 h-5" />, color: 'text-blue-500', label: '❄️ Cold' };
    } else if (trend <= -2) {
      return { icon: <TrendingDown className="w-4 h-4" />, color: 'text-orange-500', label: 'Cooling' };
    }
    return { icon: <Minus className="w-4 h-4" />, color: 'text-gray-400', label: 'Stable' };
  };

  const getPercentileStyle = (percentile: number | undefined) => {
    if (!percentile && percentile !== 0) return { color: 'text-gray-400', bg: 'bg-gray-100' };

    if (percentile >= 90) {
      return {
        color: 'text-green-700',
        bg: 'bg-gradient-to-r from-green-100 to-emerald-100',
        label: 'Elite'
      };
    } else if (percentile >= 70) {
      return {
        color: 'text-blue-700',
        bg: 'bg-gradient-to-r from-blue-100 to-sky-100',
        label: 'Plus'
      };
    } else if (percentile >= 50) {
      return {
        color: 'text-gray-700',
        bg: 'bg-gray-100',
        label: 'Average'
      };
    } else if (percentile >= 30) {
      return {
        color: 'text-orange-600',
        bg: 'bg-orange-100',
        label: 'Below Avg'
      };
    }
    return {
      color: 'text-red-600',
      bg: 'bg-red-100',
      label: 'Poor'
    };
  };

  const formatPercentile = (value: number | undefined) => {
    if (!value && value !== 0) return '--';
    return Math.round(value).toString();
  };

  const getToolGradeStyle = (grade: number | null | undefined) => {
    if (!grade) return { color: 'text-gray-400', bg: 'bg-gray-50' };

    if (grade >= 70) {
      return { color: 'text-yellow-700 font-bold', bg: 'bg-yellow-50' };
    } else if (grade >= 60) {
      return { color: 'text-blue-700 font-semibold', bg: 'bg-blue-50' };
    } else if (grade >= 50) {
      return { color: 'text-green-700 font-medium', bg: 'bg-green-50' };
    }
    return { color: 'text-gray-600', bg: 'bg-gray-50' };
  };

  const tierStyle = getTierStyle(prospect.tier);
  const trendInfo = getTrendIndicator(prospect.trend_adjustment);
  const perfData = prospect.performance_breakdown;

  // Key metrics to highlight
  const keyMetrics = isPitcher ? [
    { key: 'avg_fb_velo', label: 'Velo', icon: <Zap className="w-3 h-3" /> },
    { key: 'zone_rate', label: 'Zone%', icon: <Target className="w-3 h-3" /> },
    { key: 'hard_contact_rate', label: 'Hard%', icon: <Activity className="w-3 h-3" /> }
  ] : [
    { key: 'exit_velo_90th', label: 'EV90', icon: <Zap className="w-3 h-3" /> },
    { key: 'hard_hit_rate', label: 'Hard%', icon: <Activity className="w-3 h-3" /> },
    { key: 'contact_rate', label: 'Contact', icon: <Target className="w-3 h-3" /> }
  ];

  return (
    <div className="group relative overflow-hidden rounded-xl border border-gray-200 bg-white hover:border-gray-300 hover:shadow-xl transition-all duration-300">
      {/* Tier Banner */}
      {prospect.tier && prospect.tier <= 3 && (
        <div className={`absolute top-0 left-0 right-0 h-1 ${tierStyle.bg}`} />
      )}

      <div className="p-5">
        {/* Header Section */}
        <div className="flex items-start justify-between mb-4">
          {/* Rank and Player Info */}
          <div className="flex items-start gap-3 flex-1">
            {/* Rank Badge with gradient */}
            <div className="relative">
              <div className={`
                flex h-12 w-12 items-center justify-center rounded-full
                ${prospect.rank <= 10 ? 'bg-gradient-to-br from-purple-600 to-blue-600' :
                  prospect.rank <= 25 ? 'bg-gradient-to-br from-blue-600 to-cyan-600' :
                  prospect.rank <= 50 ? 'bg-gradient-to-br from-gray-600 to-gray-700' :
                  'bg-gray-500'}
                text-white font-bold shadow-lg
              `}>
                {prospect.rank}
              </div>
              {prospect.rank <= 3 && (
                <div className="absolute -top-1 -right-1 text-lg">
                  {prospect.rank === 1 ? '👑' : prospect.rank === 2 ? '🥈' : '🥉'}
                </div>
              )}
            </div>

            {/* Player Details */}
            <div className="flex-1 min-w-0">
              <Link
                href={`/prospects/${prospect.prospect_id}`}
                className="group/name inline-flex items-center gap-2"
              >
                <h3 className="text-lg font-bold text-gray-900 group-hover/name:text-blue-600 transition-colors truncate">
                  {prospect.name}
                </h3>
                {tierStyle.icon && <span className="text-base">{tierStyle.icon}</span>}
              </Link>

              <div className="flex items-center gap-2 mt-1 flex-wrap">
                <span className="px-2 py-0.5 bg-gray-900 text-white rounded text-xs font-semibold">
                  {prospect.position}
                </span>
                <span className="text-sm text-gray-600 font-medium">
                  {prospect.organization || 'FA'}
                </span>
                <span className="text-sm text-gray-500">
                  {prospect.level || '--'}
                </span>
                {prospect.age && (
                  <span className="text-sm text-gray-500">
                    Age {prospect.age}
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Trend Badge */}
          <div className={`flex items-center gap-1 px-3 py-1 rounded-full bg-gray-50 ${trendInfo.color}`}>
            {trendInfo.icon}
            <span className="text-sm font-medium">{trendInfo.label}</span>
          </div>
        </div>

        {/* Scores Grid - Enhanced Layout */}
        <div className="grid grid-cols-4 gap-2 mb-4">
          <div className="bg-gradient-to-br from-pink-50 to-pink-100 rounded-lg p-2 text-center">
            <div className="text-xs text-pink-600 font-medium mb-1">Base FV</div>
            <div className="text-xl font-bold text-pink-700">{prospect.base_fv.toFixed(0)}</div>
          </div>

          <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-lg p-2 text-center">
            <div className="text-xs text-purple-600 font-medium mb-1">Composite</div>
            <div className="text-xl font-bold text-purple-700">{prospect.composite_score.toFixed(1)}</div>
          </div>

          <div className={`rounded-lg p-2 text-center ${
            prospect.total_adjustment > 0 ? 'bg-gradient-to-br from-green-50 to-green-100' :
            prospect.total_adjustment < 0 ? 'bg-gradient-to-br from-red-50 to-red-100' :
            'bg-gray-100'
          }`}>
            <div className="text-xs font-medium mb-1 text-gray-600">Adjust</div>
            <div className={`text-xl font-bold ${
              prospect.total_adjustment > 0 ? 'text-green-700' :
              prospect.total_adjustment < 0 ? 'text-red-700' :
              'text-gray-700'
            }`}>
              {prospect.total_adjustment >= 0 ? '+' : ''}{prospect.total_adjustment.toFixed(1)}
            </div>
          </div>

          {perfData?.composite_percentile !== undefined && (
            <div className={`rounded-lg p-2 text-center ${getPercentileStyle(perfData.composite_percentile).bg}`}>
              <div className="text-xs font-medium mb-1 text-gray-600">Perf %ile</div>
              <div className={`text-xl font-bold ${getPercentileStyle(perfData.composite_percentile).color}`}>
                {formatPercentile(perfData.composite_percentile)}
                <span className="text-xs">th</span>
              </div>
            </div>
          )}
        </div>

        {/* Key Performance Metrics - New Section */}
        {perfData?.percentiles && (
          <div className="mb-4 p-3 bg-gray-50 rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-gray-600" />
                <span className="text-xs font-semibold text-gray-700">Key Metrics</span>
              </div>
              <span className="text-xs text-gray-500">
                {perfData.sample_size ? `${perfData.sample_size.toLocaleString()} pitches` : 'Game logs'}
              </span>
            </div>

            <div className="grid grid-cols-3 gap-2">
              {keyMetrics.map(({ key, label, icon }) => {
                const percentile = perfData.percentiles?.[key as keyof typeof perfData.percentiles];
                const value = perfData.metrics?.[key as keyof typeof perfData.metrics];
                const style = getPercentileStyle(percentile);

                return (
                  <div key={key} className={`rounded-lg px-2 py-1.5 ${style.bg}`}>
                    <div className="flex items-center gap-1 mb-1">
                      {icon}
                      <span className="text-xs font-medium text-gray-600">{label}</span>
                    </div>
                    <div className="flex items-baseline gap-1">
                      <span className={`text-lg font-bold ${style.color}`}>
                        {formatPercentile(percentile)}
                      </span>
                      <span className="text-xs text-gray-500">%ile</span>
                    </div>
                    {value !== undefined && (
                      <div className="text-xs text-gray-500">
                        {typeof value === 'number' ? value.toFixed(1) : value}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Tool Grades - Improved Layout */}
        <div className="mb-3">
          <div className="flex items-center gap-2 mb-2">
            <Award className="w-4 h-4 text-gray-600" />
            <span className="text-xs font-semibold text-gray-700">Scouting Grades</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {isPitcher ? (
              <>
                {prospect.tool_grades.fastball && (
                  <div className={`px-2 py-1 rounded text-xs font-medium ${getToolGradeStyle(prospect.tool_grades.fastball).bg}`}>
                    <span className="text-gray-500">FB:</span>
                    <span className={`ml-1 ${getToolGradeStyle(prospect.tool_grades.fastball).color}`}>
                      {prospect.tool_grades.fastball}
                    </span>
                  </div>
                )}
                {prospect.tool_grades.slider && (
                  <div className={`px-2 py-1 rounded text-xs font-medium ${getToolGradeStyle(prospect.tool_grades.slider).bg}`}>
                    <span className="text-gray-500">SL:</span>
                    <span className={`ml-1 ${getToolGradeStyle(prospect.tool_grades.slider).color}`}>
                      {prospect.tool_grades.slider}
                    </span>
                  </div>
                )}
                {prospect.tool_grades.curve && (
                  <div className={`px-2 py-1 rounded text-xs font-medium ${getToolGradeStyle(prospect.tool_grades.curve).bg}`}>
                    <span className="text-gray-500">CB:</span>
                    <span className={`ml-1 ${getToolGradeStyle(prospect.tool_grades.curve).color}`}>
                      {prospect.tool_grades.curve}
                    </span>
                  </div>
                )}
                {prospect.tool_grades.change && (
                  <div className={`px-2 py-1 rounded text-xs font-medium ${getToolGradeStyle(prospect.tool_grades.change).bg}`}>
                    <span className="text-gray-500">CH:</span>
                    <span className={`ml-1 ${getToolGradeStyle(prospect.tool_grades.change).color}`}>
                      {prospect.tool_grades.change}
                    </span>
                  </div>
                )}
                {prospect.tool_grades.command && (
                  <div className={`px-2 py-1 rounded text-xs font-medium ${getToolGradeStyle(prospect.tool_grades.command).bg}`}>
                    <span className="text-gray-500">CMD:</span>
                    <span className={`ml-1 ${getToolGradeStyle(prospect.tool_grades.command).color}`}>
                      {prospect.tool_grades.command}
                    </span>
                  </div>
                )}
              </>
            ) : (
              <>
                {prospect.tool_grades.hit && (
                  <div className={`px-2 py-1 rounded text-xs font-medium ${getToolGradeStyle(prospect.tool_grades.hit).bg}`}>
                    <span className="text-gray-500">Hit:</span>
                    <span className={`ml-1 ${getToolGradeStyle(prospect.tool_grades.hit).color}`}>
                      {prospect.tool_grades.hit}
                    </span>
                  </div>
                )}
                {prospect.tool_grades.power && (
                  <div className={`px-2 py-1 rounded text-xs font-medium ${getToolGradeStyle(prospect.tool_grades.power).bg}`}>
                    <span className="text-gray-500">Pwr:</span>
                    <span className={`ml-1 ${getToolGradeStyle(prospect.tool_grades.power).color}`}>
                      {prospect.tool_grades.power}
                    </span>
                  </div>
                )}
                {prospect.tool_grades.speed && (
                  <div className={`px-2 py-1 rounded text-xs font-medium ${getToolGradeStyle(prospect.tool_grades.speed).bg}`}>
                    <span className="text-gray-500">Spd:</span>
                    <span className={`ml-1 ${getToolGradeStyle(prospect.tool_grades.speed).color}`}>
                      {prospect.tool_grades.speed}
                    </span>
                  </div>
                )}
                {prospect.tool_grades.field && (
                  <div className={`px-2 py-1 rounded text-xs font-medium ${getToolGradeStyle(prospect.tool_grades.field).bg}`}>
                    <span className="text-gray-500">Fld:</span>
                    <span className={`ml-1 ${getToolGradeStyle(prospect.tool_grades.field).color}`}>
                      {prospect.tool_grades.field}
                    </span>
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {/* Expand Button */}
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="w-full mt-3 pt-3 border-t border-gray-200 flex items-center justify-center gap-2 text-sm text-gray-600 hover:text-blue-600 transition-colors group/button"
        >
          <Info className="w-4 h-4" />
          <span className="font-medium">{isExpanded ? 'Hide' : 'View'} Detailed Analysis</span>
          {isExpanded ? (
            <ChevronUp className="w-4 h-4 group-hover/button:transform group-hover/button:-translate-y-0.5 transition-transform" />
          ) : (
            <ChevronDown className="w-4 h-4 group-hover/button:transform group-hover/button:translate-y-0.5 transition-transform" />
          )}
        </button>

        {/* Expanded Section */}
        {isExpanded && (
          <div className="mt-4 pt-4 border-t border-gray-200 space-y-4 animate-in slide-in-from-top duration-300">
            {/* Full Performance Breakdown */}
            <div className="bg-gray-50 rounded-lg p-4">
              <PerformanceBreakdown prospect={prospect} />
            </div>

            {/* Score Components */}
            <div className="bg-gradient-to-br from-purple-50 to-blue-50 rounded-lg p-4">
              <h4 className="text-sm font-bold text-gray-900 mb-3 flex items-center gap-2">
                <Activity className="w-4 h-4" />
                Score Components
              </h4>
              <div className="space-y-2">
                {[
                  { label: 'Base FV', value: prospect.base_fv, desc: 'FanGraphs Future Value' },
                  { label: 'Performance', value: prospect.performance_modifier, desc: 'MiLB performance vs peers' },
                  { label: 'Trend', value: prospect.trend_adjustment, desc: 'Recent hot/cold streak' },
                  { label: 'Age', value: prospect.age_adjustment, desc: 'Age relative to level' }
                ].map(({ label, value, desc }) => (
                  <div key={label} className="flex items-center justify-between">
                    <div>
                      <span className="text-sm font-medium text-gray-700">{label}</span>
                      <span className="text-xs text-gray-500 ml-2">{desc}</span>
                    </div>
                    <span className={`text-sm font-bold ${
                      value > 0 ? 'text-green-600' : value < 0 ? 'text-red-600' : 'text-gray-600'
                    }`}>
                      {value >= 0 ? '+' : ''}{value.toFixed(1)}
                    </span>
                  </div>
                ))}
                <div className="pt-2 mt-2 border-t border-purple-200 flex items-center justify-between">
                  <span className="text-sm font-bold text-gray-900">Final Composite Score</span>
                  <span className="text-lg font-bold text-purple-700">{prospect.composite_score.toFixed(1)}</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}