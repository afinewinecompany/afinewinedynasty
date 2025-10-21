'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { ChevronDown, ChevronUp, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { CompositeRanking } from '@/types/prospect';
import PerformanceBreakdown from './PerformanceBreakdown';

interface CompositeRankingsCardProps {
  prospect: CompositeRanking;
}

export default function CompositeRankingsCard({ prospect }: CompositeRankingsCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const getTrendIcon = (trend: number) => {
    if (trend >= 2) {
      return <TrendingUp className="w-4 h-4 text-green-500" />;
    } else if (trend <= -2) {
      return <TrendingDown className="w-4 h-4 text-red-500" />;
    }
    return <Minus className="w-4 h-4 text-gray-400" />;
  };

  const getTrendLabel = (trend: number) => {
    if (trend >= 5) return 'Hot';
    if (trend >= 2) return 'Surging';
    if (trend <= -5) return 'Cold';
    if (trend <= -2) return 'Cooling';
    return 'Stable';
  };

  const getTierColor = (tier: number | null) => {
    switch (tier) {
      case 1:
        return 'bg-gradient-to-r from-yellow-400 to-yellow-600 text-white';
      case 2:
        return 'bg-blue-600 text-white';
      case 3:
        return 'bg-green-600 text-white';
      case 4:
        return 'bg-gray-600 text-white';
      case 5:
        return 'bg-gray-400 text-white';
      default:
        return 'bg-gray-300 text-gray-700';
    }
  };

  const getToolGradeColor = (grade: number | null | undefined) => {
    if (!grade) return 'text-gray-400';
    if (grade >= 70) return 'text-yellow-600 font-bold';
    if (grade >= 60) return 'text-blue-600 font-semibold';
    if (grade >= 50) return 'text-green-600 font-medium';
    return 'text-gray-600';
  };

  const getAdjustmentColor = (adjustment: number) => {
    if (adjustment > 0) return 'text-green-600';
    if (adjustment < 0) return 'text-red-600';
    return 'text-gray-600';
  };

  const isPitcher = prospect.position === 'SP' || prospect.position === 'RP' || prospect.position === 'P';

  return (
    <div className="rounded-lg border border-gray-200 bg-white hover:border-gray-300 hover:shadow-md transition-all duration-200">
      <div className="p-4">
        {/* Header Section */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-start gap-3 flex-1 min-w-0">
            {/* Rank Badge */}
            <div className="flex-shrink-0">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-600 text-sm font-bold text-white">
                #{prospect.rank}
              </div>
            </div>

            {/* Name and Basic Info */}
            <div className="min-w-0 flex-1">
              <Link
                href={`/prospects/${prospect.prospect_id}`}
                className="text-base font-semibold text-gray-900 hover:text-blue-600 transition-colors block truncate"
              >
                {prospect.name}
              </Link>
              <div className="flex items-center gap-2 mt-1 text-sm text-gray-600">
                <span className="px-2 py-0.5 bg-gray-100 rounded text-xs font-medium">
                  {prospect.position}
                </span>
                <span className="truncate">{prospect.organization || '-'}</span>
              </div>
              <div className="flex items-center gap-2 mt-1 text-xs text-gray-500">
                <span>{prospect.level || '-'}</span>
                <span>•</span>
                <span>Age {prospect.age || '-'}</span>
              </div>
            </div>
          </div>

          {/* Tier Badge */}
          {prospect.tier && prospect.tier_label && (
            <div className="flex-shrink-0 ml-2">
              <span className={`px-2 py-1 text-xs font-medium rounded ${getTierColor(prospect.tier)}`}>
                {prospect.tier_label}
              </span>
            </div>
          )}
        </div>

        {/* Scores Section */}
        <div className="grid grid-cols-3 gap-3 mb-3 p-3 bg-gray-50 rounded-lg">
          <div className="text-center">
            <div className="text-xs text-gray-500 mb-1">Base FV</div>
            <div className="text-lg font-semibold text-pink-600">
              {prospect.base_fv.toFixed(0)}
            </div>
          </div>
          <div className="text-center">
            <div className="text-xs text-gray-500 mb-1">Composite</div>
            <div className="text-lg font-bold text-purple-600">
              {prospect.composite_score.toFixed(1)}
            </div>
          </div>
          <div className="text-center">
            <div className="text-xs text-gray-500 mb-1">Adjustment</div>
            <div className={`text-lg font-semibold ${getAdjustmentColor(prospect.total_adjustment)}`}>
              {prospect.total_adjustment >= 0 ? '+' : ''}{prospect.total_adjustment.toFixed(1)}
            </div>
          </div>
        </div>

        {/* Performance Data Source Indicator */}
        <div className="mb-3 flex justify-center">
          <PerformanceBreakdown prospect={prospect} compact />
        </div>

        {/* Trend and Tool Grades */}
        <div className="space-y-2">
          {/* Trend */}
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-500">Trend:</span>
            <div className="flex items-center gap-1">
              {getTrendIcon(prospect.trend_adjustment)}
              <span className="text-sm font-medium text-gray-700">
                {getTrendLabel(prospect.trend_adjustment)}
              </span>
            </div>
          </div>

          {/* Tool Grades */}
          <div className="flex items-start justify-between">
            <span className="text-xs text-gray-500">Tools:</span>
            <div className="flex flex-wrap gap-2 justify-end max-w-[70%]">
              {isPitcher ? (
                <>
                  {prospect.tool_grades.fastball && (
                    <span className={`text-xs ${getToolGradeColor(prospect.tool_grades.fastball)}`}>
                      FB: {prospect.tool_grades.fastball}
                    </span>
                  )}
                  {prospect.tool_grades.slider && (
                    <span className={`text-xs ${getToolGradeColor(prospect.tool_grades.slider)}`}>
                      SL: {prospect.tool_grades.slider}
                    </span>
                  )}
                  {prospect.tool_grades.curve && (
                    <span className={`text-xs ${getToolGradeColor(prospect.tool_grades.curve)}`}>
                      CB: {prospect.tool_grades.curve}
                    </span>
                  )}
                  {prospect.tool_grades.change && (
                    <span className={`text-xs ${getToolGradeColor(prospect.tool_grades.change)}`}>
                      CH: {prospect.tool_grades.change}
                    </span>
                  )}
                  {prospect.tool_grades.command && (
                    <span className={`text-xs ${getToolGradeColor(prospect.tool_grades.command)}`}>
                      CMD: {prospect.tool_grades.command}
                    </span>
                  )}
                </>
              ) : (
                <>
                  {prospect.tool_grades.hit && (
                    <span className={`text-xs ${getToolGradeColor(prospect.tool_grades.hit)}`}>
                      Hit: {prospect.tool_grades.hit}
                    </span>
                  )}
                  {prospect.tool_grades.power && (
                    <span className={`text-xs ${getToolGradeColor(prospect.tool_grades.power)}`}>
                      Pwr: {prospect.tool_grades.power}
                    </span>
                  )}
                  {prospect.tool_grades.speed && (
                    <span className={`text-xs ${getToolGradeColor(prospect.tool_grades.speed)}`}>
                      Spd: {prospect.tool_grades.speed}
                    </span>
                  )}
                  {prospect.tool_grades.field && (
                    <span className={`text-xs ${getToolGradeColor(prospect.tool_grades.field)}`}>
                      Fld: {prospect.tool_grades.field}
                    </span>
                  )}
                </>
              )}
            </div>
          </div>
        </div>

        {/* Expand/Collapse Button */}
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="w-full mt-3 pt-3 border-t border-gray-200 flex items-center justify-center gap-1 text-sm text-gray-600 hover:text-gray-900 transition-colors"
        >
          <span>{isExpanded ? 'Hide' : 'Show'} Breakdown</span>
          {isExpanded ? (
            <ChevronUp className="w-4 h-4" />
          ) : (
            <ChevronDown className="w-4 h-4" />
          )}
        </button>

        {/* Expanded Breakdown */}
        {isExpanded && (
          <div className="mt-3 pt-3 border-t border-gray-200 space-y-4">
            {/* Score Breakdown */}
            <div>
              <h4 className="text-sm font-semibold text-gray-900 mb-2">Score Breakdown</h4>
              <div className="space-y-1.5 text-xs">
                <div className="flex justify-between items-center">
                  <span className="text-gray-600">Base FV (FanGraphs):</span>
                  <span className="font-medium text-gray-900">{prospect.base_fv.toFixed(1)}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-600">Performance Modifier:</span>
                  <span className={`font-medium ${getAdjustmentColor(prospect.performance_modifier)}`}>
                    {prospect.performance_modifier >= 0 ? '+' : ''}{prospect.performance_modifier.toFixed(1)}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-600">Trend Adjustment:</span>
                  <span className={`font-medium ${getAdjustmentColor(prospect.trend_adjustment)}`}>
                    {prospect.trend_adjustment >= 0 ? '+' : ''}{prospect.trend_adjustment.toFixed(1)}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-600">Age Adjustment:</span>
                  <span className={`font-medium ${getAdjustmentColor(prospect.age_adjustment)}`}>
                    {prospect.age_adjustment >= 0 ? '+' : ''}{prospect.age_adjustment.toFixed(1)}
                  </span>
                </div>
                <div className="flex justify-between items-center pt-2 border-t border-gray-200">
                  <span className="font-semibold text-gray-900">Composite Score:</span>
                  <span className="font-bold text-purple-600">{prospect.composite_score.toFixed(1)}</span>
                </div>
              </div>
            </div>

            {/* Insights */}
            <div>
              <h4 className="text-sm font-semibold text-gray-900 mb-2">What This Means</h4>
              <div className="space-y-1 text-xs text-gray-600">
                {prospect.performance_modifier > 5 && (
                  <div className="flex items-start gap-1">
                    <span className="text-green-600 font-semibold">•</span>
                    <span>Strong recent performance at current level</span>
                  </div>
                )}
                {prospect.performance_modifier < -5 && (
                  <div className="flex items-start gap-1">
                    <span className="text-red-600 font-semibold">•</span>
                    <span>Struggling at current level</span>
                  </div>
                )}
                {prospect.trend_adjustment >= 2 && (
                  <div className="flex items-start gap-1">
                    <span className="text-green-600 font-semibold">•</span>
                    <span>Hot streak - improving recently</span>
                  </div>
                )}
                {prospect.trend_adjustment <= -2 && (
                  <div className="flex items-start gap-1">
                    <span className="text-red-600 font-semibold">•</span>
                    <span>Cooling off - recent decline</span>
                  </div>
                )}
                {prospect.age_adjustment > 0 && (
                  <div className="flex items-start gap-1">
                    <span className="text-green-600 font-semibold">•</span>
                    <span>Young for level - advanced for age</span>
                  </div>
                )}
                {prospect.age_adjustment < 0 && (
                  <div className="flex items-start gap-1">
                    <span className="text-red-600 font-semibold">•</span>
                    <span>Old for level - organizational depth</span>
                  </div>
                )}
                {Math.abs(prospect.total_adjustment) < 1 && (
                  <div className="flex items-start gap-1">
                    <span className="text-gray-500 font-semibold">•</span>
                    <span>Performing as expected at current level</span>
                  </div>
                )}
              </div>
            </div>

            {/* Performance Breakdown */}
            <div className="pt-3 border-t border-gray-200">
              <PerformanceBreakdown prospect={prospect} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
