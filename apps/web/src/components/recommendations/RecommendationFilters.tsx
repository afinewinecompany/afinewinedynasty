/**
 * Recommendation Filters Component
 *
 * Provides filtering controls for prospect recommendations including risk tolerance,
 * position filters, ETA year range, and trade value filters.
 *
 * @component RecommendationFilters
 * @since 1.0.0
 */

'use client';

import React, { useState } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
import { Filter, X } from 'lucide-react';
import type { RecommendationFilters as FilterType } from '@/types/recommendations';

/**
 * Component props
 */
interface RecommendationFiltersProps {
  /** Current filter values */
  filters: FilterType;
  /** Callback when filters change */
  onFiltersChange: (filters: FilterType) => void;
  /** Optional callback when filters are reset */
  onReset?: () => void;
}

/**
 * Recommendation filters component
 *
 * @param props - Component props
 * @returns Rendered component
 *
 * @example
 * ```tsx
 * <RecommendationFilters
 *   filters={filters}
 *   onFiltersChange={(newFilters) => setFilters(newFilters)}
 *   onReset={() => setFilters({})}
 * />
 * ```
 *
 * @since 1.0.0
 */
export function RecommendationFilters({
  filters,
  onFiltersChange,
  onReset,
}: RecommendationFiltersProps) {
  const [localFilters, setLocalFilters] = useState<FilterType>(filters);

  /**
   * Available positions
   */
  const positions = ['SP', 'RP', 'C', '1B', '2B', '3B', 'SS', 'OF', 'DH'];

  /**
   * Available trade values
   */
  const tradeValues = ['Elite', 'High', 'Medium', 'Low', 'Speculative'];

  /**
   * Current year for ETA range
   */
  const currentYear = new Date().getFullYear();
  const minYear = currentYear;
  const maxYear = currentYear + 10;

  /**
   * Handle risk tolerance change
   */
  const handleRiskToleranceChange = (value: string) => {
    const updated = {
      ...localFilters,
      risk_tolerance: value as FilterType['risk_tolerance'],
    };
    setLocalFilters(updated);
    onFiltersChange(updated);
  };

  /**
   * Toggle position filter
   */
  const togglePosition = (position: string) => {
    const current = localFilters.positions || [];
    const updated = current.includes(position)
      ? current.filter((p) => p !== position)
      : [...current, position];

    const newFilters = {
      ...localFilters,
      positions: updated.length > 0 ? updated : undefined,
    };
    setLocalFilters(newFilters);
    onFiltersChange(newFilters);
  };

  /**
   * Toggle trade value filter
   */
  const toggleTradeValue = (value: string) => {
    const current = localFilters.trade_values || [];
    const updated = current.includes(value)
      ? current.filter((v) => v !== value)
      : [...current, value];

    const newFilters = {
      ...localFilters,
      trade_values: updated.length > 0 ? updated : undefined,
    };
    setLocalFilters(newFilters);
    onFiltersChange(newFilters);
  };

  /**
   * Handle ETA min change
   */
  const handleEtaMinChange = (value: number) => {
    const newFilters = {
      ...localFilters,
      eta_min: value,
    };
    setLocalFilters(newFilters);
    onFiltersChange(newFilters);
  };

  /**
   * Handle ETA max change
   */
  const handleEtaMaxChange = (value: number) => {
    const newFilters = {
      ...localFilters,
      eta_max: value,
    };
    setLocalFilters(newFilters);
    onFiltersChange(newFilters);
  };

  /**
   * Handle reset
   */
  const handleReset = () => {
    const emptyFilters: FilterType = {};
    setLocalFilters(emptyFilters);
    onFiltersChange(emptyFilters);
    onReset?.();
  };

  /**
   * Check if any filters are active
   */
  const hasActiveFilters = () => {
    return (
      localFilters.risk_tolerance ||
      (localFilters.positions && localFilters.positions.length > 0) ||
      localFilters.eta_min !== undefined ||
      localFilters.eta_max !== undefined ||
      (localFilters.trade_values && localFilters.trade_values.length > 0)
    );
  };

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Filter className="h-5 w-5" />
              Filter Recommendations
            </CardTitle>
            <CardDescription>
              Refine your prospect recommendations
            </CardDescription>
          </div>
          {hasActiveFilters() && (
            <Button variant="outline" size="sm" onClick={handleReset}>
              <X className="h-4 w-4 mr-1" />
              Clear All
            </Button>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Risk Tolerance Filter */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Risk Tolerance
          </label>
          <Select
            value={localFilters.risk_tolerance || 'all'}
            onValueChange={(value) => {
              if (value === 'all') {
                const updated = { ...localFilters };
                delete updated.risk_tolerance;
                setLocalFilters(updated);
                onFiltersChange(updated);
              } else {
                handleRiskToleranceChange(value);
              }
            }}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All</SelectItem>
              <SelectItem value="conservative">Conservative</SelectItem>
              <SelectItem value="balanced">Balanced</SelectItem>
              <SelectItem value="aggressive">Aggressive</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Position Filters */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-3">
            Positions
          </label>
          <div className="flex flex-wrap gap-2">
            {positions.map((position) => {
              const isSelected = localFilters.positions?.includes(position);
              return (
                <Badge
                  key={position}
                  className={`cursor-pointer transition-colors ${
                    isSelected
                      ? 'bg-blue-600 text-white hover:bg-blue-700'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                  onClick={() => togglePosition(position)}
                >
                  {position}
                </Badge>
              );
            })}
          </div>
          {localFilters.positions && localFilters.positions.length > 0 && (
            <p className="text-xs text-gray-500 mt-2">
              {localFilters.positions.length} position
              {localFilters.positions.length > 1 ? 's' : ''} selected
            </p>
          )}
        </div>

        {/* ETA Year Range */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            ETA Year Range
          </label>
          <div className="space-y-4">
            {/* Min Year */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-gray-600">Minimum ETA</span>
                <span className="text-sm font-medium text-gray-900">
                  {localFilters.eta_min || minYear}
                </span>
              </div>
              <Slider
                min={minYear}
                max={maxYear}
                value={localFilters.eta_min || minYear}
                onValueChange={handleEtaMinChange}
              />
            </div>

            {/* Max Year */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-gray-600">Maximum ETA</span>
                <span className="text-sm font-medium text-gray-900">
                  {localFilters.eta_max || maxYear}
                </span>
              </div>
              <Slider
                min={minYear}
                max={maxYear}
                value={localFilters.eta_max || maxYear}
                onValueChange={handleEtaMaxChange}
              />
            </div>
          </div>
          <p className="text-xs text-gray-500 mt-2">
            Filter prospects by expected MLB arrival year
          </p>
        </div>

        {/* Trade Value Filters */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-3">
            Trade Value
          </label>
          <div className="space-y-2">
            {tradeValues.map((value) => {
              const isSelected = localFilters.trade_values?.includes(value);
              return (
                <div key={value} className="flex items-center">
                  <Checkbox
                    checked={isSelected}
                    onChange={() => toggleTradeValue(value)}
                    label={value}
                  />
                </div>
              );
            })}
          </div>
          {localFilters.trade_values &&
            localFilters.trade_values.length > 0 && (
              <p className="text-xs text-gray-500 mt-2">
                {localFilters.trade_values.length} value tier
                {localFilters.trade_values.length > 1 ? 's' : ''} selected
              </p>
            )}
        </div>

        {/* Active Filters Summary */}
        {hasActiveFilters() && (
          <div className="p-3 rounded-lg bg-blue-50 border border-blue-200">
            <h4 className="text-sm font-medium text-blue-900 mb-2">
              Active Filters
            </h4>
            <div className="flex flex-wrap gap-2">
              {localFilters.risk_tolerance && (
                <Badge className="bg-blue-100 text-blue-800">
                  Risk: {localFilters.risk_tolerance}
                </Badge>
              )}
              {localFilters.positions && localFilters.positions.length > 0 && (
                <Badge className="bg-blue-100 text-blue-800">
                  {localFilters.positions.length} Position
                  {localFilters.positions.length > 1 ? 's' : ''}
                </Badge>
              )}
              {(localFilters.eta_min || localFilters.eta_max) && (
                <Badge className="bg-blue-100 text-blue-800">
                  ETA: {localFilters.eta_min || minYear}-
                  {localFilters.eta_max || maxYear}
                </Badge>
              )}
              {localFilters.trade_values &&
                localFilters.trade_values.length > 0 && (
                  <Badge className="bg-blue-100 text-blue-800">
                    {localFilters.trade_values.length} Value Tier
                    {localFilters.trade_values.length > 1 ? 's' : ''}
                  </Badge>
                )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
