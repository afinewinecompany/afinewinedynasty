'use client';

import { useState, useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  ReferenceLine,
} from 'recharts';
import {
  TrendingUp,
  Filter,
  Info,
  BarChart3,
  Target,
  Calendar,
} from 'lucide-react';

interface StatisticalTrendComparisonProps {
  comparisonData: any;
  selectedProspects: any[];
}

const COLORS = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6'];

const METRICS = {
  batting: [
    { value: 'batting_avg', label: 'Batting Average', format: 'decimal3' },
    { value: 'on_base_pct', label: 'On-Base %', format: 'decimal3' },
    { value: 'slugging_pct', label: 'Slugging %', format: 'decimal3' },
    { value: 'ops', label: 'OPS', format: 'decimal3' },
    { value: 'wrc_plus', label: 'wRC+', format: 'integer' },
    { value: 'walk_rate', label: 'Walk %', format: 'decimal1' },
    {
      value: 'strikeout_rate',
      label: 'Strikeout %',
      format: 'decimal1',
      reverse: true,
    },
  ],
  pitching: [
    { value: 'era', label: 'ERA', format: 'decimal2', reverse: true },
    { value: 'whip', label: 'WHIP', format: 'decimal2', reverse: true },
    { value: 'k_per_9', label: 'K/9', format: 'decimal1' },
    { value: 'bb_per_9', label: 'BB/9', format: 'decimal1', reverse: true },
    { value: 'fip', label: 'FIP', format: 'decimal2', reverse: true },
  ],
};

export default function StatisticalTrendComparison({
  comparisonData,
  selectedProspects,
}: StatisticalTrendComparisonProps) {
  const [selectedMetric, setSelectedMetric] = useState('ops');
  const [showLeagueAverage, setShowLeagueAverage] = useState(true);

  const prospects = comparisonData?.prospects || [];

  // Determine if we're comparing hitters or pitchers
  const isPitching =
    (prospects.length > 0 && prospects[0].position === 'SP') ||
    prospects[0].position === 'RP';
  const availableMetrics = isPitching ? METRICS.pitching : METRICS.batting;

  // Mock statistical history data - in production this would come from the API
  const generateMockHistoricalData = (prospect: any) => {
    const data = [];
    const baseValue = prospect.stats?.[selectedMetric] || 0.25;

    // Generate 5 data points over time
    for (let i = 0; i < 5; i++) {
      const variation = (Math.random() - 0.5) * 0.1; // ±5% variation
      const value = Math.max(0, baseValue + baseValue * variation);

      data.push({
        period: `${2020 + i}`,
        [prospect.name]: value,
        level: i < 2 ? 'A' : i < 4 ? 'AA' : 'AAA',
      });
    }

    return data;
  };

  // Prepare trend data
  const trendData = useMemo(() => {
    if (prospects.length === 0) return [];

    // Generate mock data for each prospect
    const allData = prospects.map(generateMockHistoricalData);

    // Merge data by period
    const mergedData = [];
    const periods = ['2020', '2021', '2022', '2023', '2024'];

    periods.forEach((period, index) => {
      const periodData = { period };

      prospects.forEach((prospect, prospectIndex) => {
        const prospectData = allData[prospectIndex][index];
        periodData[prospect.name] = prospectData[prospect.name];
      });

      mergedData.push(periodData);
    });

    return mergedData;
  }, [prospects, selectedMetric]);

  // League averages
  const leagueAverages = {
    batting_avg: 0.25,
    on_base_pct: 0.32,
    slugging_pct: 0.4,
    ops: 0.72,
    wrc_plus: 100,
    walk_rate: 8.5,
    strikeout_rate: 23.0,
    era: 4.0,
    whip: 1.3,
    k_per_9: 8.5,
    bb_per_9: 3.5,
    fip: 4.2,
  };

  const formatValue = (value: number, format: string) => {
    if (value === null || value === undefined) return 'N/A';

    switch (format) {
      case 'decimal3':
        return value.toFixed(3);
      case 'decimal2':
        return value.toFixed(2);
      case 'decimal1':
        return value.toFixed(1);
      case 'integer':
        return Math.round(value).toString();
      default:
        return value.toString();
    }
  };

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const selectedMetricData = availableMetrics.find(
        (m) => m.value === selectedMetric
      );

      return (
        <div className="bg-white p-4 border border-gray-200 rounded-lg shadow-lg">
          <p className="font-semibold mb-2">{label}</p>
          {payload.map((entry: any, index: number) => (
            <div key={index} className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: entry.color }}
                />
                <span className="text-sm font-medium">{entry.dataKey}:</span>
              </div>
              <span className="font-bold" style={{ color: entry.color }}>
                {formatValue(
                  entry.value,
                  selectedMetricData?.format || 'decimal2'
                )}
              </span>
            </div>
          ))}
          {showLeagueAverage && leagueAverages[selectedMetric] && (
            <div className="border-t pt-2 mt-2">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">League Avg:</span>
                <span className="font-medium text-gray-700">
                  {formatValue(
                    leagueAverages[selectedMetric],
                    selectedMetricData?.format || 'decimal2'
                  )}
                </span>
              </div>
            </div>
          )}
        </div>
      );
    }
    return null;
  };

  // Calculate trend statistics
  const trendStats = useMemo(() => {
    if (trendData.length < 2) return {};

    const stats = {};
    prospects.forEach((prospect) => {
      const values = trendData
        .map((d) => d[prospect.name])
        .filter((v) => v != null);
      if (values.length >= 2) {
        const first = values[0];
        const last = values[values.length - 1];
        const change = last - first;
        const percentChange = (change / first) * 100;

        const selectedMetricData = availableMetrics.find(
          (m) => m.value === selectedMetric
        );
        const isImproving = selectedMetricData?.reverse
          ? change < 0
          : change > 0;

        stats[prospect.name] = {
          change,
          percentChange,
          isImproving,
          trend:
            Math.abs(percentChange) > 1
              ? isImproving
                ? 'improving'
                : 'declining'
              : 'stable',
        };
      }
    });

    return stats;
  }, [trendData, prospects, selectedMetric, availableMetrics]);

  if (prospects.length < 2) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
        <div className="flex items-center gap-3">
          <Info className="w-5 h-5 text-yellow-600" />
          <div>
            <h3 className="font-medium text-yellow-800">Insufficient Data</h3>
            <p className="text-sm text-yellow-700 mt-1">
              At least 2 prospects are required for statistical trend
              comparison.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header and Controls */}
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-blue-600" />
            Statistical Trend Comparison
          </h3>
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <Calendar className="w-4 h-4" />
            5-year progression
          </div>
        </div>

        {/* Controls */}
        <div className="flex flex-wrap items-center gap-4 mb-6">
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-gray-500" />
            <select
              value={selectedMetric}
              onChange={(e) => setSelectedMetric(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              {availableMetrics.map((metric) => (
                <option key={metric.value} value={metric.value}>
                  {metric.label}
                </option>
              ))}
            </select>
          </div>

          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={showLeagueAverage}
              onChange={(e) => setShowLeagueAverage(e.target.checked)}
              className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
            />
            Show League Average
          </label>
        </div>

        {/* Trend Chart */}
        <div className="h-96 mb-6">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={trendData}
              margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis
                dataKey="period"
                tick={{ fontSize: 12 }}
                axisLine={{ stroke: '#e5e7eb' }}
              />
              <YAxis
                tick={{ fontSize: 12 }}
                axisLine={{ stroke: '#e5e7eb' }}
                label={{
                  value:
                    availableMetrics.find((m) => m.value === selectedMetric)
                      ?.label || '',
                  angle: -90,
                  position: 'insideLeft',
                }}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend />

              {prospects.map((prospect, index) => (
                <Line
                  key={prospect.id}
                  type="monotone"
                  dataKey={prospect.name}
                  stroke={COLORS[index % COLORS.length]}
                  strokeWidth={3}
                  dot={{
                    fill: COLORS[index % COLORS.length],
                    strokeWidth: 2,
                    r: 5,
                  }}
                  activeDot={{
                    r: 7,
                    stroke: COLORS[index % COLORS.length],
                    strokeWidth: 2,
                  }}
                />
              ))}

              {showLeagueAverage && leagueAverages[selectedMetric] && (
                <ReferenceLine
                  y={leagueAverages[selectedMetric]}
                  stroke="#6b7280"
                  strokeDasharray="5 5"
                  strokeWidth={2}
                  label={{
                    value: 'League Avg',
                    position: 'topRight',
                    style: { fill: '#6b7280', fontSize: '12px' },
                  }}
                />
              )}
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Trend Analysis */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {prospects.map((prospect, index) => {
            const stats = trendStats[prospect.name];
            if (!stats) return null;

            return (
              <div key={prospect.id} className="bg-gray-50 rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="font-semibold text-gray-900">
                    {prospect.name}
                  </h4>
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: COLORS[index % COLORS.length] }}
                  />
                </div>

                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Trend</span>
                    <span
                      className={`px-2 py-1 text-xs font-medium rounded-full ${
                        stats.trend === 'improving'
                          ? 'bg-green-100 text-green-800'
                          : stats.trend === 'declining'
                            ? 'bg-red-100 text-red-800'
                            : 'bg-gray-100 text-gray-800'
                      }`}
                    >
                      {stats.trend}
                    </span>
                  </div>

                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Change</span>
                    <span
                      className={`font-semibold ${
                        stats.isImproving
                          ? 'text-green-600'
                          : stats.trend === 'declining'
                            ? 'text-red-600'
                            : 'text-gray-600'
                      }`}
                    >
                      {stats.change > 0 ? '+' : ''}
                      {formatValue(
                        stats.change,
                        availableMetrics.find((m) => m.value === selectedMetric)
                          ?.format || 'decimal2'
                      )}
                    </span>
                  </div>

                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">% Change</span>
                    <span
                      className={`font-semibold ${
                        stats.isImproving
                          ? 'text-green-600'
                          : stats.trend === 'declining'
                            ? 'text-red-600'
                            : 'text-gray-600'
                      }`}
                    >
                      {stats.percentChange > 0 ? '+' : ''}
                      {stats.percentChange.toFixed(1)}%
                    </span>
                  </div>

                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Current</span>
                    <span className="font-semibold text-gray-900">
                      {formatValue(
                        prospect.stats?.[selectedMetric] ||
                          trendData[trendData.length - 1]?.[prospect.name] ||
                          0,
                        availableMetrics.find((m) => m.value === selectedMetric)
                          ?.format || 'decimal2'
                      )}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Performance Trajectory Analysis */}
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <h4 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Target className="w-5 h-5 text-purple-600" />
          Performance Trajectory Analysis
        </h4>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h5 className="font-medium text-gray-900 mb-3">
              Development Patterns
            </h5>
            <div className="space-y-2 text-sm">
              {Object.entries(trendStats).map(
                ([name, stats]: [string, any]) => (
                  <div key={name} className="flex items-center justify-between">
                    <span className="text-gray-700">{name}</span>
                    <div className="flex items-center gap-2">
                      <TrendingUp
                        className={`w-4 h-4 ${
                          stats.isImproving ? 'text-green-600' : 'text-red-600'
                        }`}
                      />
                      <span className="font-medium">{stats.trend}</span>
                    </div>
                  </div>
                )
              )}
            </div>
          </div>

          <div>
            <h5 className="font-medium text-gray-900 mb-3">League Context</h5>
            <div className="space-y-2 text-sm">
              {prospects.map((prospect) => {
                const currentValue = prospect.stats?.[selectedMetric];
                const leagueAvg = leagueAverages[selectedMetric];

                if (!currentValue || !leagueAvg) return null;

                const selectedMetricData = availableMetrics.find(
                  (m) => m.value === selectedMetric
                );
                const isAboveAverage = selectedMetricData?.reverse
                  ? currentValue < leagueAvg
                  : currentValue > leagueAvg;
                const difference = Math.abs(
                  ((currentValue - leagueAvg) / leagueAvg) * 100
                );

                return (
                  <div
                    key={prospect.id}
                    className="flex items-center justify-between"
                  >
                    <span className="text-gray-700">{prospect.name}</span>
                    <span
                      className={`font-medium ${
                        isAboveAverage ? 'text-green-600' : 'text-red-600'
                      }`}
                    >
                      {isAboveAverage ? '+' : '-'}
                      {difference.toFixed(1)}% vs avg
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        <div className="mt-4 p-3 bg-blue-50 rounded-lg">
          <p className="text-sm text-blue-800">
            <strong>Interpretation:</strong> Track development consistency and
            trajectory over time. Prospects with improving trends and
            above-average performance show positive development patterns.
            Consider both absolute performance and improvement rate when
            evaluating prospects.
          </p>
        </div>
      </div>
    </div>
  );
}
