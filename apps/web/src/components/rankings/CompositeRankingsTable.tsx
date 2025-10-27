'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { ChevronUp, ChevronDown, Info, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { CompositeRanking } from '@/types/prospect';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import PerformanceBreakdown from './PerformanceBreakdown';
import ExpandedPlayerRow from './ExpandedPlayerRow';
import ExpandedPlayerRowV2 from './ExpandedPlayerRowV2';

interface CompositeRankingsTableProps {
  prospects: CompositeRanking[];
  sortBy: string;
  sortOrder: 'asc' | 'desc';
  onSort: (column: string) => void;
}

export default function CompositeRankingsTable({
  prospects,
  sortBy,
  sortOrder,
  onSort,
}: CompositeRankingsTableProps) {
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());

  const toggleRow = (prospectId: number) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(prospectId)) {
      newExpanded.delete(prospectId);
    } else {
      newExpanded.add(prospectId);
    }
    setExpandedRows(newExpanded);
  };

  const renderSortIcon = (column: string) => {
    if (sortBy !== column) {
      return <ChevronUp className="w-4 h-4 text-muted-foreground/40" />;
    }
    return sortOrder === 'asc' ? (
      <ChevronUp className="w-4 h-4 text-wine-periwinkle" />
    ) : (
      <ChevronDown className="w-4 h-4 text-wine-periwinkle" />
    );
  };

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

  const formatToolGrades = (prospect: CompositeRanking) => {
    const isPitcher = prospect.position === 'SP' || prospect.position === 'RP' || prospect.position === 'P';

    if (isPitcher) {
      return (
        <div className="flex gap-2 text-xs">
          {prospect.tool_grades.fastball && (
            <span className={getToolGradeColor(prospect.tool_grades.fastball)}>
              FB: {prospect.tool_grades.fastball}
            </span>
          )}
          {prospect.tool_grades.slider && (
            <span className={getToolGradeColor(prospect.tool_grades.slider)}>
              SL: {prospect.tool_grades.slider}
            </span>
          )}
          {prospect.tool_grades.curve && (
            <span className={getToolGradeColor(prospect.tool_grades.curve)}>
              CB: {prospect.tool_grades.curve}
            </span>
          )}
          {prospect.tool_grades.change && (
            <span className={getToolGradeColor(prospect.tool_grades.change)}>
              CH: {prospect.tool_grades.change}
            </span>
          )}
          {prospect.tool_grades.command && (
            <span className={getToolGradeColor(prospect.tool_grades.command)}>
              CMD: {prospect.tool_grades.command}
            </span>
          )}
        </div>
      );
    }

    return (
      <div className="flex gap-2 text-xs">
        {prospect.tool_grades.hit && (
          <span className={getToolGradeColor(prospect.tool_grades.hit)}>
            Hit: {prospect.tool_grades.hit}
          </span>
        )}
        {prospect.tool_grades.power && (
          <span className={getToolGradeColor(prospect.tool_grades.power)}>
            Pwr: {prospect.tool_grades.power}
          </span>
        )}
        {prospect.tool_grades.speed && (
          <span className={getToolGradeColor(prospect.tool_grades.speed)}>
            Spd: {prospect.tool_grades.speed}
          </span>
        )}
        {prospect.tool_grades.field && (
          <span className={getToolGradeColor(prospect.tool_grades.field)}>
            Fld: {prospect.tool_grades.field}
          </span>
        )}
      </div>
    );
  };

  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="min-w-full divide-y divide-border">
        <thead className="bg-card">
          <tr>
            {/* Rank */}
            <th
              onClick={() => onSort('rank')}
              className="px-3 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider cursor-pointer hover:bg-muted/50 transition-colors"
            >
              <div className="flex items-center gap-1">
                <span>Rank</span>
                {renderSortIcon('rank')}
              </div>
            </th>

            {/* Name */}
            <th
              onClick={() => onSort('name')}
              className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider cursor-pointer hover:bg-muted/50 transition-colors"
            >
              <div className="flex items-center gap-1">
                <span>Name</span>
                {renderSortIcon('name')}
              </div>
            </th>

            {/* Position */}
            <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Pos
            </th>

            {/* Organization */}
            <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Org
            </th>

            {/* Level */}
            <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Level
            </th>

            {/* Age */}
            <th
              onClick={() => onSort('age')}
              className="px-3 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider cursor-pointer hover:bg-muted/50 transition-colors"
            >
              <div className="flex items-center gap-1">
                <span>Age</span>
                {renderSortIcon('age')}
              </div>
            </th>

            {/* Base FV */}
            <th
              onClick={() => onSort('base_fv')}
              className="px-3 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider cursor-pointer hover:bg-muted/50 transition-colors"
            >
              <div className="flex items-center gap-1">
                <span>FV</span>
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger>
                      <Info className="w-3 h-3 text-muted-foreground/60 hover:text-accent transition-colors" />
                    </TooltipTrigger>
                    <TooltipContent className="bg-popover border-border">
                      <p className="max-w-xs text-popover-foreground">
                        FanGraphs Future Value (40-70 scale)
                      </p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
                {renderSortIcon('base_fv')}
              </div>
            </th>

            {/* Composite Score */}
            <th
              onClick={() => onSort('composite_score')}
              className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider cursor-pointer hover:bg-muted/50 transition-colors"
            >
              <div className="flex items-center gap-1">
                <span>Composite</span>
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger>
                      <Info className="w-3 h-3 text-muted-foreground/60 hover:text-accent transition-colors" />
                    </TooltipTrigger>
                    <TooltipContent className="bg-popover border-border">
                      <p className="max-w-xs text-popover-foreground">
                        FV + Performance + Trend + Age adjustments
                      </p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
                {renderSortIcon('composite_score')}
              </div>
            </th>

            {/* Adjustment */}
            <th
              onClick={() => onSort('total_adjustment')}
              className="px-3 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider cursor-pointer hover:bg-muted/50 transition-colors"
            >
              <div className="flex items-center gap-1">
                <span>Adj</span>
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger>
                      <Info className="w-3 h-3 text-muted-foreground/60 hover:text-accent transition-colors" />
                    </TooltipTrigger>
                    <TooltipContent className="bg-popover border-border">
                      <p className="max-w-xs text-popover-foreground">
                        Total adjustment from base FV
                      </p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
                {renderSortIcon('total_adjustment')}
              </div>
            </th>

            {/* Performance Data */}
            <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
              <div className="flex items-center gap-1">
                <span>Data</span>
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger>
                      <Info className="w-3 h-3 text-muted-foreground/60 hover:text-accent transition-colors" />
                    </TooltipTrigger>
                    <TooltipContent className="bg-popover border-border">
                      <p className="max-w-xs text-popover-foreground">
                        Performance data source: Pitch Data (best) or Game Logs (fallback)
                      </p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>
            </th>

            {/* Trend */}
            <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Trend
            </th>

            {/* Tool Grades */}
            <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Tool Grades
            </th>

            {/* Tier */}
            <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Tier
            </th>
          </tr>
        </thead>

        <tbody className="bg-background divide-y divide-border">
          {prospects.map((prospect) => (
            <React.Fragment key={prospect.prospect_id}>
              <tr
                className="hover:bg-muted/30 transition-colors group cursor-pointer"
                onClick={() => toggleRow(prospect.prospect_id)}
              >
                {/* Rank */}
                <td className="px-3 py-4 whitespace-nowrap text-sm text-foreground">
                  <span className="font-semibold text-wine-cyan">#{prospect.rank}</span>
                </td>

                {/* Name */}
                <td className="px-6 py-4 whitespace-nowrap">
                  <Link
                    href={`/prospects/${prospect.prospect_id}`}
                    className="text-sm font-medium text-primary hover:text-wine-rose transition-colors"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {prospect.name}
                  </Link>
                </td>

                {/* Position */}
                <td className="px-3 py-4 whitespace-nowrap text-sm">
                  <span className="px-2 py-1 text-xs font-medium rounded-full bg-muted text-muted-foreground border border-border">
                    {prospect.position}
                  </span>
                </td>

                {/* Organization */}
                <td className="px-6 py-4 whitespace-nowrap text-sm text-foreground">
                  {prospect.organization || '-'}
                </td>

                {/* Level */}
                <td className="px-3 py-4 whitespace-nowrap text-sm text-foreground">
                  {prospect.level || '-'}
                </td>

                {/* Age */}
                <td className="px-3 py-4 whitespace-nowrap text-sm text-foreground">
                  {prospect.age || '-'}
                </td>

                {/* Base FV */}
                <td className="px-3 py-4 whitespace-nowrap text-sm">
                  <span className="font-medium text-wine-rose">
                    {prospect.base_fv.toFixed(0)}
                  </span>
                </td>

                {/* Composite Score */}
                <td className="px-4 py-4 whitespace-nowrap">
                  <span className="text-sm font-semibold text-wine-periwinkle">
                    {prospect.composite_score.toFixed(1)}
                  </span>
                </td>

                {/* Adjustment */}
                <td className="px-3 py-4 whitespace-nowrap text-sm">
                  <span className={`font-medium ${getAdjustmentColor(prospect.total_adjustment)}`}>
                    {prospect.total_adjustment >= 0 ? '+' : ''}{prospect.total_adjustment.toFixed(1)}
                  </span>
                </td>

                {/* Performance Data Source */}
                <td className="px-3 py-4 whitespace-nowrap">
                  <PerformanceBreakdown prospect={prospect} compact />
                </td>

                {/* Trend */}
                <td className="px-3 py-4 whitespace-nowrap">
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger>
                        <div className="flex items-center gap-1">
                          {getTrendIcon(prospect.trend_adjustment)}
                          <span className="text-xs text-muted-foreground">
                            {getTrendLabel(prospect.trend_adjustment)}
                          </span>
                        </div>
                      </TooltipTrigger>
                      <TooltipContent className="bg-popover border-border">
                        <p className="text-popover-foreground">
                          {prospect.trend_adjustment >= 0 ? '+' : ''}{prospect.trend_adjustment.toFixed(1)} trend adjustment
                        </p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </td>

                {/* Tool Grades */}
                <td className="px-6 py-4 whitespace-nowrap">
                  {formatToolGrades(prospect)}
                </td>

                {/* Tier */}
                <td className="px-3 py-4 whitespace-nowrap">
                  {prospect.tier && prospect.tier_label && (
                    <span className={`px-2 py-1 text-xs font-medium rounded ${getTierColor(prospect.tier)}`}>
                      {prospect.tier_label}
                    </span>
                  )}
                </td>
              </tr>

              {/* Expanded Row: Modern Performance Analysis with Comparative Percentiles */}
              {expandedRows.has(prospect.prospect_id) && (
                <ExpandedPlayerRowV2 prospect={prospect} />
              )}
            </React.Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}
