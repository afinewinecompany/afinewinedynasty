'use client';

import React, { useState, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  ReferenceLine,
  ScatterChart,
  Scatter,
  BarChart,
  Bar
} from 'recharts';
import {
  TrendingUp,
  Calendar,
  BarChart3,
  Target,
  Filter,
  Info,
  Award,
  AlertTriangle,
  ArrowUp,
  ArrowDown,
  Minus
} from 'lucide-react';

interface StatRecord {
  date: string;
  level: string;
  games: number;
  batting?: {
    avg: number;
    obp: number;
    slg: number;
    ops: number;
    hr: number;
    rbi: number;
    sb: number;
    k_rate: number;
    bb_rate: number;
    woba?: number;
    wrc_plus?: number;
  };
  pitching?: {
    era: number;
    whip: number;
    k_rate: number;
    bb_rate: number;
    k_9: number;
    bb_9: number;
    fip?: number;
    xfip?: number;
    innings: number;
    wins: number;
    losses: number;
    saves: number;
  };
}

interface PerformanceTrendsProps {
  statsHistory: {
    by_level: Record<string, { aggregation: any; latest: StatRecord; count: number }>;
    by_season: Record<string, { aggregation: any; count: number; levels: string[] }>;
    progression: any;
    latest_stats: StatRecord;
  };
  prospectName: string;
  position: string;
  className?: string;
}

export function PerformanceTrends({
  statsHistory,
  prospectName,
  position,
  className = ''
}: PerformanceTrendsProps) {
  const [selectedMetric, setSelectedMetric] = useState('ops');
  const [selectedTimeframe, setSelectedTimeframe] = useState('all');
  const [activeTab, setActiveTab] = useState('trends');

  const isPitcher = position === 'SP' || position === 'RP' || position.includes('P');

  // Available metrics based on position
  const battingMetrics = [
    { value: 'ops', label: 'OPS', format: 'decimal3' },
    { value: 'avg', label: 'Batting Average', format: 'decimal3' },
    { value: 'obp', label: 'On-Base %', format: 'decimal3' },
    { value: 'slg', label: 'Slugging %', format: 'decimal3' },
    { value: 'wrc_plus', label: 'wRC+', format: 'integer' },
    { value: 'k_rate', label: 'K%', format: 'decimal1' },
    { value: 'bb_rate', label: 'BB%', format: 'decimal1' }
  ];

  const pitchingMetrics = [
    { value: 'era', label: 'ERA', format: 'decimal2' },
    { value: 'whip', label: 'WHIP', format: 'decimal2' },
    { value: 'k_rate', label: 'K%', format: 'decimal1' },
    { value: 'bb_rate', label: 'BB%', format: 'decimal1' },
    { value: 'k_9', label: 'K/9', format: 'decimal1' },
    { value: 'fip', label: 'FIP', format: 'decimal2' }
  ];

  const availableMetrics = isPitcher ? pitchingMetrics : battingMetrics;

  // Format value based on metric type
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

  // Prepare trend data
  const trendData = useMemo(() => {
    const data: any[] = [];

    // Add data from by_season
    Object.entries(statsHistory.by_season).forEach(([year, seasonData]) => {
      const aggregation = seasonData.aggregation;

      if (isPitcher && aggregation.pitching) {
        data.push({
          period: year,
          type: 'season',
          level: seasonData.levels.join(', '),
          games: aggregation.pitching.games,
          era: aggregation.pitching.era,
          whip: aggregation.pitching.whip,
          k_rate: aggregation.pitching.k_rate,
          bb_rate: aggregation.pitching.bb_rate,
          k_9: aggregation.pitching.k_rate * 9 / 100, // Approximate
          fip: aggregation.pitching.fip || aggregation.pitching.era
        });
      } else if (!isPitcher && aggregation.batting) {
        data.push({
          period: year,
          type: 'season',
          level: seasonData.levels.join(', '),
          games: aggregation.batting.games,
          avg: aggregation.batting.avg,
          obp: aggregation.batting.obp,
          slg: aggregation.batting.slg,
          ops: aggregation.batting.ops,
          wrc_plus: aggregation.batting.wrc_plus || 100,
          k_rate: aggregation.batting.k_rate || 20,
          bb_rate: aggregation.batting.bb_rate || 8
        });
      }
    });

    return data.sort((a, b) => parseInt(a.period) - parseInt(b.period));
  }, [statsHistory, isPitcher]);

  // Prepare level progression data
  const levelData = useMemo(() => {
    const levels = ['Rookie', 'A', 'A+', 'AA', 'AAA'];
    const data: any[] = [];

    Object.entries(statsHistory.by_level).forEach(([level, levelInfo]) => {
      const aggregation = levelInfo.aggregation;
      const levelOrder = levels.indexOf(level);

      if (levelOrder >= 0) {
        if (isPitcher && aggregation.pitching) {
          data.push({
            level,
            levelOrder,
            games: aggregation.pitching.games,
            era: aggregation.pitching.era,
            whip: aggregation.pitching.whip,
            k_rate: aggregation.pitching.k_rate,
            bb_rate: aggregation.pitching.bb_rate,
            k_9: aggregation.pitching.k_rate * 9 / 100,
            fip: aggregation.pitching.fip || aggregation.pitching.era
          });
        } else if (!isPitcher && aggregation.batting) {
          data.push({
            level,
            levelOrder,
            games: aggregation.batting.games,
            avg: aggregation.batting.avg,
            obp: aggregation.batting.obp,
            slg: aggregation.batting.slg,
            ops: aggregation.batting.ops,
            wrc_plus: aggregation.batting.wrc_plus || 100,
            k_rate: aggregation.batting.k_rate || 20,
            bb_rate: aggregation.batting.bb_rate || 8
          });
        }
      }
    });

    return data.sort((a, b) => a.levelOrder - b.levelOrder);
  }, [statsHistory, isPitcher]);

  // Calculate league averages (placeholder values)
  const leagueAverages: Record<string, number> = isPitcher ? {
    era: 4.00,
    whip: 1.30,
    k_rate: 22.0,
    bb_rate: 9.0,
    k_9: 8.5,
    fip: 4.20
  } : {
    avg: 0.250,
    obp: 0.320,
    slg: 0.400,
    ops: 0.720,
    wrc_plus: 100,
    k_rate: 23.0,
    bb_rate: 8.5
  };

  // Get trend direction
  const getTrendDirection = (data: any[], metric: string) => {
    if (data.length < 2) return null;

    const first = data[0][metric];
    const last = data[data.length - 1][metric];

    if (first === null || last === null) return null;

    // For ERA, WHIP, lower is better
    const lowerIsBetter = ['era', 'whip', 'bb_rate'].includes(metric);

    if (Math.abs(last - first) < 0.01) return 'stable';

    if (lowerIsBetter) {
      return last < first ? 'improving' : 'declining';
    } else {
      return last > first ? 'improving' : 'declining';
    }
  };

  const getTrendIcon = (direction: string | null) => {
    switch (direction) {
      case 'improving':
        return <ArrowUp className="h-4 w-4 text-green-600" />;
      case 'declining':
        return <ArrowDown className="h-4 w-4 text-red-600" />;
      case 'stable':
        return <Minus className="h-4 w-4 text-gray-600" />;
      default:
        return null;
    }
  };

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      const selectedMetricData = availableMetrics.find(m => m.value === selectedMetric);

      return (
        <div className="bg-white p-3 border border-gray-200 rounded-lg shadow-lg">
          <p className="font-semibold mb-2">{label}</p>
          {data.level && <p className="text-sm text-gray-600">Level: {data.level}</p>}
          <p className="text-sm">
            <span className="font-medium">{selectedMetricData?.label}: </span>
            <span className="font-bold text-blue-600">
              {formatValue(payload[0].value, selectedMetricData?.format || 'decimal2')}
            </span>
          </p>
          {data.games && <p className="text-xs text-gray-500">{data.games} games</p>}
        </div>
      );
    }
    return null;
  };

  return (
    <Card className={`w-full ${className}`}>
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center space-x-2">
            <TrendingUp className="h-5 w-5 text-blue-600" />
            <span>Performance Trends</span>
          </CardTitle>
          {statsHistory.progression && (
            <Badge variant="outline" className="flex items-center space-x-1">
              <Calendar className="h-3 w-3" />
              <span>{statsHistory.progression.total_games} total games</span>
            </Badge>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Controls */}
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center space-x-2">
            <Filter className="h-4 w-4 text-gray-500" />
            <Select value={selectedMetric} onValueChange={setSelectedMetric}>
              <SelectTrigger className="w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {availableMetrics.map(metric => (
                  <SelectItem key={metric.value} value={metric.value}>
                    {metric.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="trends">Timeline Trends</TabsTrigger>
            <TabsTrigger value="levels">Level Progression</TabsTrigger>
            <TabsTrigger value="analysis">Performance Analysis</TabsTrigger>
          </TabsList>

          <TabsContent value="trends" className="space-y-4">
            {trendData.length > 0 ? (
              <div className="space-y-4">
                <ResponsiveContainer width="100%" height={400}>
                  <LineChart data={trendData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="period" />
                    <YAxis />
                    <Tooltip content={<CustomTooltip />} />
                    <Line
                      type="monotone"
                      dataKey={selectedMetric}
                      stroke="#3b82f6"
                      strokeWidth={3}
                      dot={{ fill: '#3b82f6', strokeWidth: 2, r: 6 }}
                      activeDot={{ r: 8 }}
                    />
                    {leagueAverages[selectedMetric] && (
                      <ReferenceLine
                        y={leagueAverages[selectedMetric]}
                        stroke="#ef4444"
                        strokeDasharray="5 5"
                        label={{ value: "League Avg", position: "topRight" }}
                      />
                    )}
                  </LineChart>
                </ResponsiveContainer>

                {/* Trend Summary */}
                <div className="bg-gray-50 rounded-lg p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      {getTrendIcon(getTrendDirection(trendData, selectedMetric))}
                      <span className="font-medium">
                        {availableMetrics.find(m => m.value === selectedMetric)?.label} Trend
                      </span>
                    </div>
                    <div className="text-sm text-gray-600">
                      {trendData.length} data points
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                No trend data available
              </div>
            )}
          </TabsContent>

          <TabsContent value="levels" className="space-y-4">
            {levelData.length > 0 ? (
              <div className="space-y-4">
                <ResponsiveContainer width="100%" height={400}>
                  <BarChart data={levelData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="level" />
                    <YAxis />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar
                      dataKey={selectedMetric}
                      fill="#8b5cf6"
                      radius={[4, 4, 0, 0]}
                    />
                    {leagueAverages[selectedMetric] && (
                      <ReferenceLine
                        y={leagueAverages[selectedMetric]}
                        stroke="#ef4444"
                        strokeDasharray="5 5"
                        label={{ value: "League Avg", position: "topRight" }}
                      />
                    )}
                  </BarChart>
                </ResponsiveContainer>

                {/* Level Summary */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {levelData.map((level, index) => {
                    const selectedMetricData = availableMetrics.find(m => m.value === selectedMetric);
                    const value = level[selectedMetric];
                    const leagueAvg = leagueAverages[selectedMetric];

                    let performance = 'average';
                    if (leagueAvg) {
                      const isLowerBetter = ['era', 'whip', 'bb_rate'].includes(selectedMetric);
                      if (isLowerBetter) {
                        performance = value < leagueAvg * 0.9 ? 'above' : value > leagueAvg * 1.1 ? 'below' : 'average';
                      } else {
                        performance = value > leagueAvg * 1.1 ? 'above' : value < leagueAvg * 0.9 ? 'below' : 'average';
                      }
                    }

                    return (
                      <div key={index} className="bg-gray-50 rounded-lg p-4">
                        <div className="text-center">
                          <div className="font-semibold text-gray-900">{level.level}</div>
                          <div className={`text-xl font-bold ${
                            performance === 'above' ? 'text-green-600' :
                            performance === 'below' ? 'text-red-600' : 'text-gray-600'
                          }`}>
                            {formatValue(value, selectedMetricData?.format || 'decimal2')}
                          </div>
                          <div className="text-xs text-gray-500">{level.games} games</div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                No level progression data available
              </div>
            )}
          </TabsContent>

          <TabsContent value="analysis" className="space-y-4">
            {/* Performance Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Key Metrics */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-lg flex items-center space-x-2">
                    <Target className="h-4 w-4" />
                    <span>Key Metrics</span>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {availableMetrics.slice(0, 4).map(metric => {
                    const latest = statsHistory.latest_stats;
                    const value = isPitcher
                      ? latest?.pitching?.[metric.value as keyof typeof latest.pitching]
                      : latest?.batting?.[metric.value as keyof typeof latest.batting];

                    const leagueAvg = leagueAverages[metric.value];
                    let performance = 'average';

                    if (value && leagueAvg) {
                      const isLowerBetter = ['era', 'whip', 'bb_rate'].includes(metric.value);
                      if (isLowerBetter) {
                        performance = value < leagueAvg * 0.9 ? 'above' : value > leagueAvg * 1.1 ? 'below' : 'average';
                      } else {
                        performance = value > leagueAvg * 1.1 ? 'above' : value < leagueAvg * 0.9 ? 'below' : 'average';
                      }
                    }

                    return (
                      <div key={metric.value} className="flex items-center justify-between">
                        <span className="text-sm font-medium">{metric.label}</span>
                        <div className="flex items-center space-x-2">
                          <span className={`font-semibold ${
                            performance === 'above' ? 'text-green-600' :
                            performance === 'below' ? 'text-red-600' : 'text-gray-600'
                          }`}>
                            {value ? formatValue(value, metric.format) : 'N/A'}
                          </span>
                          {performance === 'above' && <ArrowUp className="h-3 w-3 text-green-600" />}
                          {performance === 'below' && <ArrowDown className="h-3 w-3 text-red-600" />}
                        </div>
                      </div>
                    );
                  })}
                </CardContent>
              </Card>

              {/* Development Trends */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-lg flex items-center space-x-2">
                    <BarChart3 className="h-4 w-4" />
                    <span>Development Trends</span>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {statsHistory.progression && (
                    <>
                      <div className="flex items-center justify-between">
                        <span className="text-sm">Total Games</span>
                        <span className="font-semibold">{statsHistory.progression.total_games}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-sm">Time Span</span>
                        <span className="font-semibold">{statsHistory.progression.time_span_days} days</span>
                      </div>
                      {!isPitcher && statsHistory.progression.batting && (
                        <>
                          <div className="flex items-center justify-between">
                            <span className="text-sm">AVG Change</span>
                            <span className={`font-semibold ${
                              statsHistory.progression.batting.avg_change > 0 ? 'text-green-600' :
                              statsHistory.progression.batting.avg_change < 0 ? 'text-red-600' : 'text-gray-600'
                            }`}>
                              {statsHistory.progression.batting.avg_change > 0 ? '+' : ''}
                              {statsHistory.progression.batting.avg_change.toFixed(3)}
                            </span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-sm">OPS Change</span>
                            <span className={`font-semibold ${
                              (statsHistory.progression.batting.obp_change + statsHistory.progression.batting.slg_change) > 0 ? 'text-green-600' :
                              (statsHistory.progression.batting.obp_change + statsHistory.progression.batting.slg_change) < 0 ? 'text-red-600' : 'text-gray-600'
                            }`}>
                              {(statsHistory.progression.batting.obp_change + statsHistory.progression.batting.slg_change) > 0 ? '+' : ''}
                              {(statsHistory.progression.batting.obp_change + statsHistory.progression.batting.slg_change).toFixed(3)}
                            </span>
                          </div>
                        </>
                      )}
                      {isPitcher && statsHistory.progression.pitching && (
                        <>
                          <div className="flex items-center justify-between">
                            <span className="text-sm">ERA Change</span>
                            <span className={`font-semibold ${
                              statsHistory.progression.pitching.era_change < 0 ? 'text-green-600' :
                              statsHistory.progression.pitching.era_change > 0 ? 'text-red-600' : 'text-gray-600'
                            }`}>
                              {statsHistory.progression.pitching.era_change > 0 ? '+' : ''}
                              {statsHistory.progression.pitching.era_change.toFixed(2)}
                            </span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-sm">K% Change</span>
                            <span className={`font-semibold ${
                              statsHistory.progression.pitching.k_rate_change > 0 ? 'text-green-600' :
                              statsHistory.progression.pitching.k_rate_change < 0 ? 'text-red-600' : 'text-gray-600'
                            }`}>
                              {statsHistory.progression.pitching.k_rate_change > 0 ? '+' : ''}
                              {statsHistory.progression.pitching.k_rate_change.toFixed(1)}%
                            </span>
                          </div>
                        </>
                      )}
                    </>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* Performance Notes */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <div className="flex items-start space-x-2">
                <Info className="h-5 w-5 text-blue-600 mt-0.5 flex-shrink-0" />
                <div>
                  <h4 className="font-semibold text-blue-900 mb-2">Performance Analysis</h4>
                  <p className="text-blue-800 text-sm">
                    Track {prospectName}'s statistical development across different levels and timeframes.
                    Green indicates above-average performance, red indicates below-average, based on typical
                    minor league benchmarks. Use the timeline and level views to identify development patterns.
                  </p>
                </div>
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}