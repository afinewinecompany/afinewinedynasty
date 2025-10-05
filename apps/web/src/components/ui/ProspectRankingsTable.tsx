'use client';

import React from 'react';
import Link from 'next/link';
import { ChevronUp, ChevronDown, Info } from 'lucide-react';
import { ProspectRanking } from '@/types/prospect';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from './tooltip';

interface ProspectRankingsTableProps {
  prospects: ProspectRanking[];
  sortBy: string;
  sortOrder: 'asc' | 'desc';
  onSort: (column: string) => void;
}

export default function ProspectRankingsTable({
  prospects,
  sortBy,
  sortOrder,
  onSort,
}: ProspectRankingsTableProps) {
  const renderSortIcon = (column: string) => {
    if (sortBy !== column) {
      return <ChevronUp className="w-4 h-4 text-gray-400" />;
    }
    return sortOrder === 'asc' ? (
      <ChevronUp className="w-4 h-4 text-blue-600" />
    ) : (
      <ChevronDown className="w-4 h-4 text-blue-600" />
    );
  };

  const getConfidenceColor = (level: string) => {
    switch (level) {
      case 'High':
        return 'text-green-600';
      case 'Medium':
        return 'text-yellow-600';
      case 'Low':
        return 'text-red-600';
      default:
        return 'text-gray-600';
    }
  };

  const getConfidenceDot = (level: string) => {
    const color = getConfidenceColor(level);
    return <span className={`text-2xl ${color}`}>●</span>;
  };

  const formatNumber = (
    value: number | null | undefined,
    decimals: number = 3
  ) => {
    if (value === null || value === undefined) return '-';
    return value.toFixed(decimals);
  };

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            {/* Rank */}
            <th
              onClick={() => onSort('dynasty_rank')}
              className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
            >
              <div className="flex items-center gap-1">
                <span>Rank</span>
                {renderSortIcon('dynasty_rank')}
              </div>
            </th>

            {/* Name */}
            <th
              onClick={() => onSort('name')}
              className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
            >
              <div className="flex items-center gap-1">
                <span>Name</span>
                {renderSortIcon('name')}
              </div>
            </th>

            {/* Position */}
            <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Pos
            </th>

            {/* Organization */}
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Organization
            </th>

            {/* Level */}
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Level
            </th>

            {/* Age */}
            <th
              onClick={() => onSort('age')}
              className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
            >
              <div className="flex items-center gap-1">
                <span>Age</span>
                {renderSortIcon('age')}
              </div>
            </th>

            {/* ETA */}
            <th
              onClick={() => onSort('eta_year')}
              className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
            >
              <div className="flex items-center gap-1">
                <span>ETA</span>
                {renderSortIcon('eta_year')}
              </div>
            </th>

            {/* Dynasty Score */}
            <th
              onClick={() => onSort('dynasty_score')}
              className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
            >
              <div className="flex items-center gap-1">
                <span>Score</span>
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger>
                      <Info className="w-3 h-3 text-gray-400" />
                    </TooltipTrigger>
                    <TooltipContent>
                      <p className="max-w-xs">
                        Dynasty Score combines ML predictions (35%), scouting
                        grades (25%), age factor (20%), performance (15%), and
                        ETA (5%)
                      </p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
                {renderSortIcon('dynasty_score')}
              </div>
            </th>

            {/* ML Indicator */}
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              ML
            </th>

            {/* Stats */}
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Key Stats
            </th>

            {/* Grade */}
            <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              FV
            </th>
          </tr>
        </thead>

        <tbody className="bg-white divide-y divide-gray-200">
          {prospects.map((prospect) => (
            <tr key={prospect.id} className="hover:bg-gray-50">
              {/* Rank */}
              <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-900">
                <span className="font-semibold">{prospect.dynastyRank}</span>
              </td>

              {/* Name */}
              <td className="px-6 py-4 whitespace-nowrap">
                <Link
                  href={`/prospects/${prospect.id}`}
                  className="text-sm font-medium text-blue-600 hover:text-blue-800"
                >
                  {prospect.name}
                </Link>
              </td>

              {/* Position */}
              <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-900">
                <span className="px-2 py-1 text-xs font-medium rounded-full bg-gray-100">
                  {prospect.position}
                </span>
              </td>

              {/* Organization */}
              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                {prospect.organization || '-'}
              </td>

              {/* Level */}
              <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900">
                {prospect.level || '-'}
              </td>

              {/* Age */}
              <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-900">
                {prospect.age || '-'}
              </td>

              {/* ETA */}
              <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-900">
                {prospect.etaYear || '-'}
              </td>

              {/* Dynasty Score */}
              <td className="px-4 py-4 whitespace-nowrap">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-gray-900">
                    {prospect.dynastyScore.toFixed(1)}
                  </span>
                  <div className="flex flex-col text-xs text-gray-500">
                    <span>ML: {prospect.mlScore.toFixed(0)}</span>
                    <span>Scout: {prospect.scoutingScore.toFixed(0)}</span>
                  </div>
                </div>
              </td>

              {/* ML Indicator */}
              <td className="px-4 py-4 whitespace-nowrap">
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger>
                      {getConfidenceDot(prospect.confidenceLevel)}
                    </TooltipTrigger>
                    <TooltipContent>
                      <p className="font-medium">{prospect.confidenceLevel} Confidence</p>
                      <p className="text-xs text-gray-400">ML Success Probability</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </td>

              {/* Stats */}
              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                {prospect.position === 'SP' || prospect.position === 'RP' ? (
                  <div className="flex flex-col text-xs">
                    <span>ERA: {formatNumber(prospect.era, 2)}</span>
                    <span>WHIP: {formatNumber(prospect.whip, 2)}</span>
                  </div>
                ) : (
                  <div className="flex flex-col text-xs">
                    <span>AVG: {formatNumber(prospect.battingAvg)}</span>
                    <span>OBP: {formatNumber(prospect.onBasePct)}</span>
                  </div>
                )}
              </td>

              {/* Future Value */}
              <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-900">
                {prospect.futureValue ? (
                  <span className="font-medium">{prospect.futureValue}</span>
                ) : (
                  '-'
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
