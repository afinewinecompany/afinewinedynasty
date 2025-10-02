'use client';

import { useState } from 'react';
import {
  ChevronDown,
  ChevronRight,
  TrendingUp,
  TrendingDown,
  Minus,
} from 'lucide-react';
import { ComparisonData, ComparisonProspect } from '@/types/prospect';
import MLPredictionComparison from './MLPredictionComparison';
import StatisticalTrendComparison from './StatisticalTrendComparison';
import ScoutingRadarComparison from './ScoutingRadarComparison';
import HistoricalAnalogComparison from './HistoricalAnalogComparison';

interface ComparisonTableProps {
  comparisonData: ComparisonData;
  selectedProspects: ComparisonProspect[];
}

interface MetricRow {
  label: string;
  key: string;
  category: string;
  format?: 'number' | 'percentage' | 'decimal';
  reverse?: boolean; // true if lower is better (e.g., ERA)
}

const METRIC_CATEGORIES = {
  basic: 'Basic Information',
  dynasty: 'Dynasty Metrics',
  batting: 'Batting Statistics',
  pitching: 'Pitching Statistics',
  scouting: 'Scouting Grades',
  ml: 'ML Predictions',
};

const METRICS: MetricRow[] = [
  // Basic Info
  { label: 'Position', key: 'position', category: 'basic' },
  { label: 'Organization', key: 'organization', category: 'basic' },
  { label: 'Level', key: 'level', category: 'basic' },
  { label: 'Age', key: 'age', category: 'basic' },
  { label: 'ETA Year', key: 'eta_year', category: 'basic' },

  // Dynasty Metrics
  {
    label: 'Dynasty Score',
    key: 'dynasty_metrics.dynasty_score',
    category: 'dynasty',
    format: 'number',
  },
  {
    label: 'ML Score',
    key: 'dynasty_metrics.ml_score',
    category: 'dynasty',
    format: 'number',
  },
  {
    label: 'Scouting Score',
    key: 'dynasty_metrics.scouting_score',
    category: 'dynasty',
    format: 'number',
  },
  {
    label: 'Confidence Level',
    key: 'dynasty_metrics.confidence_level',
    category: 'dynasty',
  },

  // Batting Stats
  {
    label: 'Batting Average',
    key: 'stats.batting_avg',
    category: 'batting',
    format: 'decimal',
  },
  {
    label: 'On-Base Percentage',
    key: 'stats.on_base_pct',
    category: 'batting',
    format: 'decimal',
  },
  {
    label: 'Slugging Percentage',
    key: 'stats.slugging_pct',
    category: 'batting',
    format: 'decimal',
  },
  { label: 'OPS', key: 'stats.ops', category: 'batting', format: 'decimal' },
  {
    label: 'wRC+',
    key: 'stats.wrc_plus',
    category: 'batting',
    format: 'number',
  },
  {
    label: 'Walk Rate',
    key: 'stats.walk_rate',
    category: 'batting',
    format: 'percentage',
  },
  {
    label: 'Strikeout Rate',
    key: 'stats.strikeout_rate',
    category: 'batting',
    format: 'percentage',
    reverse: true,
  },

  // Pitching Stats
  {
    label: 'ERA',
    key: 'stats.era',
    category: 'pitching',
    format: 'decimal',
    reverse: true,
  },
  {
    label: 'WHIP',
    key: 'stats.whip',
    category: 'pitching',
    format: 'decimal',
    reverse: true,
  },
  {
    label: 'K/9',
    key: 'stats.k_per_9',
    category: 'pitching',
    format: 'decimal',
  },
  {
    label: 'BB/9',
    key: 'stats.bb_per_9',
    category: 'pitching',
    format: 'decimal',
    reverse: true,
  },
  {
    label: 'FIP',
    key: 'stats.fip',
    category: 'pitching',
    format: 'decimal',
    reverse: true,
  },

  // Scouting Grades
  {
    label: 'Overall Grade',
    key: 'scouting_grades.overall',
    category: 'scouting',
    format: 'number',
  },
  {
    label: 'Future Value',
    key: 'scouting_grades.future_value',
    category: 'scouting',
    format: 'number',
  },
  {
    label: 'Hit Tool',
    key: 'scouting_grades.hit',
    category: 'scouting',
    format: 'number',
  },
  {
    label: 'Power Tool',
    key: 'scouting_grades.power',
    category: 'scouting',
    format: 'number',
  },
  {
    label: 'Speed Tool',
    key: 'scouting_grades.speed',
    category: 'scouting',
    format: 'number',
  },
  {
    label: 'Field Tool',
    key: 'scouting_grades.field',
    category: 'scouting',
    format: 'number',
  },
  {
    label: 'Arm Tool',
    key: 'scouting_grades.arm',
    category: 'scouting',
    format: 'number',
  },

  // ML Predictions
  {
    label: 'Success Probability',
    key: 'ml_prediction.success_probability',
    category: 'ml',
    format: 'percentage',
  },
  {
    label: 'ML Confidence',
    key: 'ml_prediction.confidence_level',
    category: 'ml',
  },
];

export default function ComparisonTable({
  comparisonData,
  selectedProspects,
}: ComparisonTableProps) {
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(
    new Set(['basic', 'dynasty'])
  );

  const prospects = comparisonData?.prospects || [];

  const toggleCategory = (category: string) => {
    setExpandedCategories((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(category)) {
        newSet.delete(category);
      } else {
        newSet.add(category);
      }
      return newSet;
    });
  };

  const getValue = (prospect: ComparisonProspect, key: string): unknown => {
    const keys = key.split('.');
    let value = prospect;
    for (const k of keys) {
      value = value?.[k];
    }
    return value;
  };

  const formatValue = (value: unknown, format?: string): string => {
    if (value === null || value === undefined) return '—';
    if (typeof value === 'string') return value;

    switch (format) {
      case 'percentage':
        return typeof value === 'number'
          ? `${(value * 100).toFixed(1)}%`
          : value;
      case 'decimal':
        return typeof value === 'number' ? value.toFixed(3) : value;
      case 'number':
        return typeof value === 'number' ? value.toFixed(1) : value;
      default:
        return value.toString();
    }
  };

  const getAdvantageIndicator = (
    values: unknown[],
    reverse = false
  ): (string | null)[] => {
    const numericValues = values
      .map((v) => (typeof v === 'number' ? v : null))
      .filter((v) => v !== null);

    if (numericValues.length < 2) return values.map(() => null);

    const max = Math.max(...numericValues);
    const min = Math.min(...numericValues);

    return values.map((value) => {
      if (typeof value !== 'number') return null;

      if (reverse) {
        if (value === min) return 'best';
        if (value === max) return 'worst';
      } else {
        if (value === max) return 'best';
        if (value === min) return 'worst';
      }

      // Calculate if it's significantly different
      const range = max - min;
      const threshold = range * 0.1; // 10% threshold

      if (reverse) {
        if (value <= min + threshold) return 'good';
        if (value >= max - threshold) return 'poor';
      } else {
        if (value >= max - threshold) return 'good';
        if (value <= min + threshold) return 'poor';
      }

      return 'neutral';
    });
  };

  const getIndicatorIcon = (indicator: string | null) => {
    switch (indicator) {
      case 'best':
        return <TrendingUp className="w-4 h-4 text-green-600" />;
      case 'good':
        return <TrendingUp className="w-4 h-4 text-green-500" />;
      case 'worst':
        return <TrendingDown className="w-4 h-4 text-red-600" />;
      case 'poor':
        return <TrendingDown className="w-4 h-4 text-red-500" />;
      default:
        return <Minus className="w-4 h-4 text-gray-400" />;
    }
  };

  const getIndicatorColor = (indicator: string | null) => {
    switch (indicator) {
      case 'best':
        return 'bg-green-50 border-green-200';
      case 'good':
        return 'bg-green-25 border-green-100';
      case 'worst':
        return 'bg-red-50 border-red-200';
      case 'poor':
        return 'bg-red-25 border-red-100';
      default:
        return '';
    }
  };

  // Group metrics by category
  const metricsByCategory = METRICS.reduce(
    (acc, metric) => {
      if (!acc[metric.category]) {
        acc[metric.category] = [];
      }
      acc[metric.category].push(metric);
      return acc;
    },
    {} as Record<string, MetricRow[]>
  );

  // Filter out categories that don't have data for any prospect
  const hasDataForCategory = (category: string, metrics: MetricRow[]) => {
    return metrics.some((metric) =>
      prospects.some((prospect) => getValue(prospect, metric.key) != null)
    );
  };

  return (
    <div className="p-6">
      <div className="mb-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-2">
          Prospect Comparison Analysis
        </h3>
        <p className="text-sm text-gray-600">
          Comparing {prospects.length} prospects • Generated{' '}
          {new Date(
            comparisonData.comparison_metadata.generated_at
          ).toLocaleString()}
        </p>
      </div>

      <div className="space-y-6">
        {Object.entries(metricsByCategory).map(([category, metrics]) => {
          if (!hasDataForCategory(category, metrics)) return null;

          const isExpanded = expandedCategories.has(category);

          return (
            <div
              key={category}
              className="border border-gray-200 rounded-lg overflow-hidden"
            >
              <button
                onClick={() => toggleCategory(category)}
                className="w-full flex items-center justify-between p-4 bg-gray-50 hover:bg-gray-100 transition-colors"
              >
                <h4 className="font-medium text-gray-900">
                  {METRIC_CATEGORIES[category]}
                </h4>
                {isExpanded ? (
                  <ChevronDown className="w-5 h-5 text-gray-500" />
                ) : (
                  <ChevronRight className="w-5 h-5 text-gray-500" />
                )}
              </button>

              {isExpanded && (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-gray-25">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Metric
                        </th>
                        {prospects.map((prospect) => (
                          <th
                            key={prospect.id}
                            className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider"
                          >
                            <div className="space-y-1">
                              <div className="font-semibold text-gray-900">
                                {prospect.name}
                              </div>
                              <div className="text-xs text-gray-500">
                                {prospect.position} • {prospect.organization}
                              </div>
                            </div>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {metrics.map((metric) => {
                        const values = prospects.map((prospect) =>
                          getValue(prospect, metric.key)
                        );
                        const hasAnyValue = values.some((v) => v != null);

                        if (!hasAnyValue) return null;

                        const indicators = getAdvantageIndicator(
                          values,
                          metric.reverse
                        );

                        return (
                          <tr key={metric.key} className="hover:bg-gray-50">
                            <td className="px-4 py-3 text-sm font-medium text-gray-900">
                              {metric.label}
                            </td>
                            {values.map((value, prospectIndex) => {
                              const indicator = indicators[prospectIndex];
                              const colorClass = getIndicatorColor(indicator);

                              return (
                                <td
                                  key={prospectIndex}
                                  className={`px-4 py-3 text-sm text-center border-l border-r ${colorClass}`}
                                >
                                  <div className="flex items-center justify-center gap-2">
                                    <span className="text-gray-900">
                                      {formatValue(value, metric.format)}
                                    </span>
                                    {getIndicatorIcon(indicator)}
                                  </div>
                                </td>
                              );
                            })}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Statistical Trend Comparison */}
      <div className="mt-8">
        <StatisticalTrendComparison
          comparisonData={comparisonData}
          selectedProspects={selectedProspects}
        />
      </div>

      {/* Scouting Radar Comparison */}
      <div className="mt-8">
        <ScoutingRadarComparison
          comparisonData={comparisonData}
          selectedProspects={selectedProspects}
        />
      </div>

      {/* Historical Analog Comparison */}
      <div className="mt-8">
        <HistoricalAnalogComparison
          comparisonData={comparisonData}
          selectedProspects={selectedProspects}
        />
      </div>

      {/* ML Prediction Comparison */}
      <div className="mt-8">
        <MLPredictionComparison
          comparisonData={comparisonData}
          selectedProspects={selectedProspects}
        />
      </div>

      {/* Comparison Insights */}
      {comparisonData.statistical_comparison && (
        <div className="mt-8 p-6 bg-blue-50 rounded-lg">
          <h4 className="font-semibold text-blue-900 mb-3">
            Comparison Insights
          </h4>
          <div className="space-y-2 text-sm text-blue-800">
            {comparisonData.statistical_comparison.performance_gaps
              ?.slice(0, 3)
              .map((gap, index) => (
                <div key={index} className="flex items-center justify-between">
                  <span>
                    <strong>{gap.leader}</strong> leads in{' '}
                    {gap.metric.replace('_', ' ')}
                  </span>
                  <span className="font-medium">
                    +{gap.percentage_gap}% over {gap.trailing_prospect}
                  </span>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}
