'use client';

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import {
  Activity,
  Target,
  TrendingUp,
  Eye,
  Zap,
  AlertCircle,
} from 'lucide-react';

interface PitchMetrics {
  // Basic contact metrics
  contact_rate?: number;
  whiff_rate?: number;
  in_play_rate?: number;
  productive_swing_rate?: number;
  chase_rate?: number;

  // Count leverage metrics
  two_strike_contact_rate?: number;
  first_pitch_swing_rate?: number;
  ahead_swing_rate?: number;
  behind_contact_rate?: number;

  // Composite scores
  discipline_score?: number;
  power_score?: number;

  // Batted ball metrics
  line_drive_rate?: number;
  ground_ball_rate?: number;
  fly_ball_rate?: number;
  hard_hit_rate?: number;
  pull_rate?: number;
  center_rate?: number;
  oppo_rate?: number;
  pull_fly_ball_rate?: number;
  spray_ability?: number;
}

interface PitchMetricsDisplayProps {
  metrics: PitchMetrics;
  percentiles: Record<string, number>;
  sampleSize: number;
  level: string;
  comprehensiveMetrics?: boolean;
  battedBallData?: {
    with_trajectory: number;
    with_hardness: number;
    with_hit_location: number;
  };
}

export function PitchMetricsDisplay({
  metrics,
  percentiles,
  sampleSize,
  level,
  comprehensiveMetrics = false,
  battedBallData,
}: PitchMetricsDisplayProps) {
  const getPercentileColor = (percentile: number) => {
    if (percentile >= 80) return 'text-green-600 bg-green-50';
    if (percentile >= 60) return 'text-blue-600 bg-blue-50';
    if (percentile >= 40) return 'text-yellow-600 bg-yellow-50';
    return 'text-red-600 bg-red-50';
  };

  const getPercentileBadge = (percentile: number) => {
    if (percentile >= 80) return 'Elite';
    if (percentile >= 60) return 'Above Avg';
    if (percentile >= 40) return 'Average';
    return 'Below Avg';
  };

  const formatMetric = (value: number | undefined, suffix: string = '%') => {
    if (value === undefined || value === null) return 'N/A';
    return `${value.toFixed(1)}${suffix}`;
  };

  const MetricRow = ({
    label,
    value,
    percentile,
    icon: Icon,
  }: {
    label: string;
    value: number | undefined;
    percentile: number | undefined;
    icon?: React.ElementType;
  }) => {
    if (value === undefined || percentile === undefined) return null;

    return (
      <div className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
        <div className="flex items-center space-x-2">
          {Icon && <Icon className="h-4 w-4 text-gray-500" />}
          <span className="text-sm font-medium text-gray-700">{label}</span>
        </div>
        <div className="flex items-center space-x-3">
          <span className="text-sm font-bold text-gray-900">
            {formatMetric(value)}
          </span>
          <Badge
            variant="outline"
            className={`text-xs font-semibold ${getPercentileColor(percentile)}`}
          >
            {percentile.toFixed(0)}%ile
          </Badge>
        </div>
      </div>
    );
  };

  const CompositeScoreCard = ({
    title,
    score,
    percentile,
    icon: Icon,
    description,
  }: {
    title: string;
    score: number | undefined;
    percentile: number | undefined;
    icon: React.ElementType;
    description: string;
  }) => {
    if (score === undefined || percentile === undefined) return null;

    return (
      <Card className="border-2">
        <CardContent className="pt-6">
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-center space-x-2">
              <Icon className="h-5 w-5 text-blue-600" />
              <div>
                <h3 className="font-semibold text-gray-900">{title}</h3>
                <p className="text-xs text-gray-500 mt-1">{description}</p>
              </div>
            </div>
          </div>
          <div className="space-y-3">
            <div className="flex items-end justify-between">
              <div>
                <div className="text-3xl font-bold text-gray-900">
                  {score.toFixed(1)}
                </div>
                <div className="text-xs text-gray-500">Raw Score</div>
              </div>
              <div className="text-right">
                <Badge
                  className={`text-sm font-bold ${getPercentileColor(percentile)}`}
                >
                  {getPercentileBadge(percentile)}
                </Badge>
                <div className="text-xs text-gray-500 mt-1">
                  {percentile.toFixed(0)}th percentile
                </div>
              </div>
            </div>
            <Progress value={percentile} className="h-2" />
          </div>
        </CardContent>
      </Card>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header with sample size */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Activity className="h-5 w-5 text-blue-600" />
          <h2 className="text-xl font-bold text-gray-900">
            Pitch-Level Performance Metrics
          </h2>
        </div>
        <div className="text-right">
          <div className="text-sm font-semibold text-gray-900">
            {sampleSize} pitches
          </div>
          <div className="text-xs text-gray-500">{level} Level</div>
        </div>
      </div>

      {/* Composite Scores */}
      {(metrics.discipline_score !== undefined ||
        metrics.power_score !== undefined) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <CompositeScoreCard
            title="Discipline Score"
            score={metrics.discipline_score}
            percentile={percentiles.discipline_score}
            icon={Eye}
            description="Composite of contact rate, whiff rate, chase rate, and plate discipline"
          />
          {comprehensiveMetrics && (
            <CompositeScoreCard
              title="Power Score"
              score={metrics.power_score}
              percentile={percentiles.power_score}
              icon={Zap}
              description="Composite of hard hit rate, fly ball rate, and pull fly ball rate"
            />
          )}
        </div>
      )}

      {/* Contact Skills */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg flex items-center space-x-2">
            <Target className="h-4 w-4" />
            <span>Contact Skills</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-1">
          <MetricRow
            label="Contact Rate"
            value={metrics.contact_rate}
            percentile={percentiles.contact_rate}
          />
          <MetricRow
            label="Whiff Rate"
            value={metrics.whiff_rate}
            percentile={percentiles.whiff_rate}
          />
          <MetricRow
            label="In-Play Rate"
            value={metrics.in_play_rate}
            percentile={percentiles.in_play_rate}
          />
          <MetricRow
            label="Productive Swing Rate"
            value={metrics.productive_swing_rate}
            percentile={percentiles.productive_swing_rate}
          />
          {metrics.chase_rate !== undefined && (
            <MetricRow
              label="Chase Rate"
              value={metrics.chase_rate}
              percentile={percentiles.chase_rate || 50}
            />
          )}
        </CardContent>
      </Card>

      {/* Count Leverage */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg flex items-center space-x-2">
            <TrendingUp className="h-4 w-4" />
            <span>Count Leverage</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-1">
          <MetricRow
            label="Two-Strike Contact"
            value={metrics.two_strike_contact_rate}
            percentile={percentiles.two_strike_contact}
          />
          <MetricRow
            label="First Pitch Swing Rate"
            value={metrics.first_pitch_swing_rate}
            percentile={percentiles.first_pitch_approach}
          />
          <MetricRow
            label="Ahead in Count Swing Rate"
            value={metrics.ahead_swing_rate}
            percentile={percentiles.ahead_selectivity}
          />
          <MetricRow
            label="Behind in Count Contact"
            value={metrics.behind_contact_rate}
            percentile={percentiles.behind_contact}
          />
        </CardContent>
      </Card>

      {/* Batted Ball Profile */}
      {comprehensiveMetrics && battedBallData && (
        <>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-lg flex items-center space-x-2">
                <Activity className="h-4 w-4" />
                <span>Batted Ball Profile</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-1">
              <MetricRow
                label="Line Drive Rate"
                value={metrics.line_drive_rate}
                percentile={percentiles.line_drive_rate}
              />
              <MetricRow
                label="Ground Ball Rate"
                value={metrics.ground_ball_rate}
                percentile={percentiles.ground_ball_rate}
              />
              <MetricRow
                label="Fly Ball Rate"
                value={metrics.fly_ball_rate}
                percentile={percentiles.fly_ball_rate}
              />
              <MetricRow
                label="Hard Hit Rate"
                value={metrics.hard_hit_rate}
                percentile={percentiles.hard_hit_rate}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-lg flex items-center space-x-2">
                <Target className="h-4 w-4" />
                <span>Spray Chart & Power</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-1">
              <MetricRow
                label="Pull Rate"
                value={metrics.pull_rate}
                percentile={percentiles.pull_rate || 50}
              />
              <MetricRow
                label="Center Rate"
                value={metrics.center_rate}
                percentile={percentiles.center_rate || 50}
              />
              <MetricRow
                label="Opposite Field Rate"
                value={metrics.oppo_rate}
                percentile={percentiles.oppo_rate || 50}
              />
              <MetricRow
                label="Spray Ability (Balance)"
                value={metrics.spray_ability}
                percentile={percentiles.spray_ability}
              />
              <MetricRow
                label="Pull Fly Ball Rate"
                value={metrics.pull_fly_ball_rate}
                percentile={percentiles.pull_fly_ball_rate}
              />
            </CardContent>
          </Card>

          {/* Data Quality Note */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
            <div className="flex items-start space-x-2">
              <AlertCircle className="h-4 w-4 text-blue-600 mt-0.5 flex-shrink-0" />
              <div className="text-sm text-blue-800">
                <p className="font-semibold mb-1">Batted Ball Data Coverage</p>
                <p className="text-xs">
                  Trajectory data: {battedBallData.with_trajectory} balls in
                  play • Hardness data: {battedBallData.with_hardness} contacts •
                  Location data: {battedBallData.with_hit_location} hits
                </p>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
