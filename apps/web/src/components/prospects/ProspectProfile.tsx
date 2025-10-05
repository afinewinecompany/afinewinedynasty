'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useProspectProfile } from '@/hooks/useProspectProfile';
import { ProspectProfile as ProspectProfileType } from '@/types/prospect';
import LoadingSpinner from '@/components/ui/LoadingSpinner';
import ErrorMessage from '@/components/ui/ErrorMessage';
import ProspectOutlook from './ProspectOutlook';
import { MLPredictionExplanation } from './MLPredictionExplanation';
import { ScoutingRadar } from './ScoutingRadar';
import { PerformanceTrends } from './PerformanceTrends';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { SocialShare } from '@/components/ui/SocialShare';
import { Share2, Star, TrendingUp, Users, ExternalLink, Calendar, ArrowLeft } from 'lucide-react';

interface ProspectProfileProps {
  id: string;
}

interface TabsProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
  tabs: { id: string; name: string; count?: number }[];
}

function Tabs({ activeTab, onTabChange, tabs }: TabsProps) {
  return (
    <div className="border-b border-gray-200">
      <nav className="-mb-px flex space-x-8" aria-label="Tabs">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            className={`${
              activeTab === tab.id
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'
            } flex whitespace-nowrap border-b-2 py-2 px-1 text-sm font-medium`}
          >
            {tab.name}
            {tab.count !== undefined && (
              <span
                className={`${
                  activeTab === tab.id
                    ? 'bg-blue-100 text-blue-600'
                    : 'bg-gray-100 text-gray-900'
                } ml-2 rounded-full py-0.5 px-2.5 text-xs font-medium`}
              >
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </nav>
    </div>
  );
}

interface MLPredictionCardProps {
  prediction?: ProspectProfileType['ml_prediction'];
}

function MLPredictionCard({ prediction }: MLPredictionCardProps) {
  if (!prediction) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">
          ML Prediction
        </h3>
        <p className="text-gray-500">No prediction data available</p>
      </div>
    );
  }

  const getConfidenceColor = (confidence: string) => {
    switch (confidence) {
      case 'High':
        return 'bg-green-100 text-green-800';
      case 'Medium':
        return 'bg-yellow-100 text-yellow-800';
      case 'Low':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getProbabilityColor = (probability: number) => {
    if (probability >= 0.7) return 'text-green-600';
    if (probability >= 0.4) return 'text-yellow-600';
    return 'text-red-600';
  };

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">
        MLB Success Probability
      </h3>
      <div className="space-y-4">
        <div>
          <div className="w-full bg-gray-200 rounded-full h-3 mb-3">
            <div
              className={`h-3 rounded-full transition-all ${
                prediction.success_probability >= 0.7
                  ? 'bg-green-500'
                  : prediction.success_probability >= 0.4
                    ? 'bg-yellow-500'
                    : 'bg-red-500'
              }`}
              style={{ width: `${prediction.success_probability * 100}%` }}
            />
          </div>
          <div className="flex items-center justify-between">
            <span
              className={`text-3xl font-bold ${getProbabilityColor(
                prediction.success_probability
              )}`}
            >
              {Math.round(prediction.success_probability * 100)}%
            </span>
            <span
              className={`inline-flex rounded-full px-3 py-1 text-sm font-semibold ${getConfidenceColor(
                prediction.confidence_level
              )}`}
            >
              {prediction.confidence_level.toUpperCase()} CONFIDENCE
            </span>
          </div>
        </div>
        {prediction.explanation && (
          <div className="pt-3 border-t border-gray-200">
            <p className="text-sm text-gray-700 leading-relaxed italic">
              &ldquo;{prediction.explanation}&rdquo;
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

interface OverviewTabProps {
  prospect: ProspectProfileType;
}

function OverviewTab({ prospect }: OverviewTabProps) {
  return (
    <div className="space-y-6">
      {/* AI Outlook Section */}
      <ProspectOutlook prospectId={prospect.id.toString()} />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Basic Information */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Basic Information</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex justify-between">
              <span className="text-sm text-gray-600">Position</span>
              <Badge variant="outline">{prospect.position}</Badge>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-gray-600">Organization</span>
              <span className="text-sm font-medium">
                {prospect.organization}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-gray-600">Level</span>
              <span className="text-sm font-medium">{prospect.level}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-gray-600">Age</span>
              <span className="text-sm font-medium">{prospect.age}</span>
            </div>
            {prospect.eta_year && (
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">ETA Year</span>
                <span className="text-sm font-medium">{prospect.eta_year}</span>
              </div>
            )}
            {prospect.dynasty_rank && (
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Dynasty Rank</span>
                <Badge variant="secondary">#{prospect.dynasty_rank}</Badge>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Dynasty Metrics */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center space-x-2">
              <Star className="h-4 w-4" />
              <span>Dynasty Metrics</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">
                {prospect.dynasty_score?.toFixed(1) || 'N/A'}
              </div>
              <div className="text-sm text-gray-600">Dynasty Score</div>
            </div>
            <div className="grid grid-cols-2 gap-3 text-center">
              <div>
                <div className="text-lg font-semibold text-green-600">
                  {prospect.ml_score?.toFixed(1) || 'N/A'}
                </div>
                <div className="text-xs text-gray-600">ML Score</div>
              </div>
              <div>
                <div className="text-lg font-semibold text-purple-600">
                  {prospect.scouting_score?.toFixed(1) || 'N/A'}
                </div>
                <div className="text-xs text-gray-600">Scouting</div>
              </div>
            </div>
            {prospect.confidence_level && (
              <div className="text-center">
                <Badge
                  variant={
                    prospect.confidence_level === 'High'
                      ? 'default'
                      : prospect.confidence_level === 'Medium'
                        ? 'secondary'
                        : 'outline'
                  }
                >
                  {prospect.confidence_level} Confidence
                </Badge>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Quick Actions */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Quick Actions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Button
              variant="outline"
              className="w-full justify-start"
              size="sm"
            >
              <Star className="h-4 w-4 mr-2" />
              Add to Watchlist
            </Button>
            <SocialShare
              url={`/prospects/${prospect.id}`}
              title={`${prospect.name} - ${prospect.position} Prospect Profile`}
              description={`Check out ${prospect.name}'s comprehensive prospect profile with ML predictions, scouting grades, and statistical analysis on A Fine Wine Dynasty.`}
              hashtags={[
                'BaseballProspects',
                'DynastyFantasy',
                'MLB',
                prospect.organization.replace(/\s+/g, ''),
                prospect.position,
              ]}
              className="w-full"
              size="sm"
            />
            <Button
              variant="outline"
              className="w-full justify-start"
              size="sm"
            >
              <ExternalLink className="h-4 w-4 mr-2" />
              View on MLB.com
            </Button>
            <Button
              variant="outline"
              className="w-full justify-start"
              size="sm"
            >
              <TrendingUp className="h-4 w-4 mr-2" />
              Compare Players
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Enhanced ML Prediction */}
      {prospect.ml_prediction && (
        <MLPredictionExplanation
          prediction={prospect.ml_prediction}
          prospectName={prospect.name}
        />
      )}
    </div>
  );
}

interface StatisticsTabProps {
  prospect: ProspectProfileType;
}

function StatisticsTab({ prospect }: StatisticsTabProps) {
  // Mock data structure for PerformanceTrends component since we need to match the expected interface
  const mockStatsHistory = {
    by_level: {},
    by_season: {},
    progression: {
      total_games: prospect.stats?.length || 0,
      time_span_days: 365,
      batting: {
        avg_change: 0.025,
        obp_change: 0.03,
        slg_change: 0.045,
      },
      pitching: {
        era_change: -0.35,
        k_rate_change: 2.5,
        whip_change: -0.08,
        bb_rate_change: -1.2,
      },
    },
    latest_stats: prospect.stats?.[prospect.stats.length - 1] || null,
  };

  if (!prospect.stats || prospect.stats.length === 0) {
    return (
      <div className="text-center py-12">
        <svg
          className="mx-auto h-12 w-12 text-gray-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
          />
        </svg>
        <h3 className="mt-2 text-sm font-medium text-gray-900">
          No statistics available
        </h3>
        <p className="mt-1 text-sm text-gray-500">
          Statistics will appear here when available.
        </p>
      </div>
    );
  }

  const latestStats = prospect.stats[prospect.stats.length - 1];
  const isHitter =
    latestStats.at_bats !== undefined || latestStats.batting_avg !== undefined;
  const isPitcher =
    latestStats.innings_pitched !== undefined || latestStats.era !== undefined;

  return (
    <div className="space-y-6">
      {/* Current Season Summary */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Current Season Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {isHitter && (
              <>
                {latestStats.batting_avg && (
                  <div className="text-center">
                    <div className="text-2xl font-bold text-gray-900">
                      {latestStats.batting_avg.toFixed(3)}
                    </div>
                    <div className="text-sm text-gray-600">AVG</div>
                  </div>
                )}
                {latestStats.on_base_pct && (
                  <div className="text-center">
                    <div className="text-2xl font-bold text-gray-900">
                      {latestStats.on_base_pct.toFixed(3)}
                    </div>
                    <div className="text-sm text-gray-600">OBP</div>
                  </div>
                )}
                {latestStats.slugging_pct && (
                  <div className="text-center">
                    <div className="text-2xl font-bold text-gray-900">
                      {latestStats.slugging_pct.toFixed(3)}
                    </div>
                    <div className="text-sm text-gray-600">SLG</div>
                  </div>
                )}
                <div className="text-center">
                  <div className="text-2xl font-bold text-gray-900">
                    {(
                      (latestStats.on_base_pct || 0) +
                      (latestStats.slugging_pct || 0)
                    ).toFixed(3)}
                  </div>
                  <div className="text-sm text-gray-600">OPS</div>
                </div>
              </>
            )}
            {isPitcher && (
              <>
                {latestStats.era && (
                  <div className="text-center">
                    <div className="text-2xl font-bold text-gray-900">
                      {latestStats.era.toFixed(2)}
                    </div>
                    <div className="text-sm text-gray-600">ERA</div>
                  </div>
                )}
                {latestStats.whip && (
                  <div className="text-center">
                    <div className="text-2xl font-bold text-gray-900">
                      {latestStats.whip.toFixed(2)}
                    </div>
                    <div className="text-sm text-gray-600">WHIP</div>
                  </div>
                )}
                {latestStats.strikeouts_per_nine && (
                  <div className="text-center">
                    <div className="text-2xl font-bold text-gray-900">
                      {latestStats.strikeouts_per_nine.toFixed(1)}
                    </div>
                    <div className="text-sm text-gray-600">K/9</div>
                  </div>
                )}
                {latestStats.innings_pitched && (
                  <div className="text-center">
                    <div className="text-2xl font-bold text-gray-900">
                      {latestStats.innings_pitched.toFixed(1)}
                    </div>
                    <div className="text-sm text-gray-600">IP</div>
                  </div>
                )}
              </>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Performance Trends Component */}
      <PerformanceTrends
        statsHistory={mockStatsHistory}
        prospectName={prospect.name}
        position={prospect.position}
      />
    </div>
  );
}

interface ScoutingTabProps {
  prospect: ProspectProfileType;
}

function ScoutingTab({ prospect }: ScoutingTabProps) {
  // Mock scouting data since we need to match the expected interface
  const mockScoutingGrades = [
    {
      source: 'Fangraphs',
      overall: prospect.scouting_grade || 55,
      future_value: prospect.future_value || 50,
      hit: 55,
      power: 60,
      speed: 50,
      field: 55,
      arm: 60,
      updated_at: new Date().toISOString(),
    },
    {
      source: 'MLB Pipeline',
      overall: (prospect.scouting_grade || 55) - 5,
      future_value: (prospect.future_value || 50) - 5,
      hit: 50,
      power: 55,
      speed: 55,
      field: 50,
      arm: 55,
      updated_at: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(),
    },
  ];

  return (
    <div className="space-y-6">
      <ScoutingRadar
        scoutingGrades={mockScoutingGrades}
        prospectName={prospect.name}
        position={prospect.position}
      />
    </div>
  );
}

function ComparisonsTab({ prospect }: { prospect: ProspectProfileType }) {
  // Mock comparison data
  const mockComparisons = {
    current_comparisons: [
      {
        prospect: {
          id: 1,
          name: 'Similar Player 1',
          organization: 'Yankees',
          level: 'AA',
          position: prospect.position,
          age: prospect.age + 1,
          eta_year: prospect.eta_year,
        },
        similarity_score: 0.875,
        matching_features: ['age', 'level', 'batting_avg', 'obp'],
        latest_stats: {
          batting: { avg: 0.285, obp: 0.365, slg: 0.445, ops: 0.81 },
        },
        scouting_grade: { overall: 60, future_value: 55 },
      },
      {
        prospect: {
          id: 2,
          name: 'Similar Player 2',
          organization: 'Dodgers',
          level: 'AAA',
          position: prospect.position,
          age: prospect.age - 1,
          eta_year: prospect.eta_year - 1,
        },
        similarity_score: 0.823,
        matching_features: ['position', 'power', 'speed'],
        latest_stats: {
          batting: { avg: 0.267, obp: 0.342, slg: 0.478, ops: 0.82 },
        },
        scouting_grade: { overall: 55, future_value: 50 },
      },
    ],
    historical_comparisons: [
      {
        player_name: 'Historical Comp 1',
        similarity_score: 0.892,
        age_at_similar_level: prospect.age,
        mlb_outcome: {
          reached_mlb: true,
          peak_war: 25.4,
          all_star_appearances: 3,
          career_ops: 0.835,
        },
        minor_league_stats_at_age: {
          avg: 0.278,
          obp: 0.355,
          slg: 0.445,
        },
      },
    ],
  };

  return (
    <div className="space-y-6">
      {/* Current Comparisons */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <Users className="h-5 w-5" />
            <span>Current Prospect Comparisons</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {mockComparisons.current_comparisons.map((comp, index) => (
            <div key={index} className="border border-gray-200 rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h4 className="font-semibold text-gray-900">
                    {comp.prospect.name}
                  </h4>
                  <p className="text-sm text-gray-600">
                    {comp.prospect.organization} • {comp.prospect.level} • Age{' '}
                    {comp.prospect.age}
                  </p>
                </div>
                <Badge variant="secondary">
                  {(comp.similarity_score * 100).toFixed(1)}% Similar
                </Badge>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {comp.latest_stats?.batting && (
                  <>
                    <div className="text-center">
                      <div className="text-lg font-bold text-gray-900">
                        {comp.latest_stats.batting.avg.toFixed(3)}
                      </div>
                      <div className="text-xs text-gray-600">AVG</div>
                    </div>
                    <div className="text-center">
                      <div className="text-lg font-bold text-gray-900">
                        {comp.latest_stats.batting.obp.toFixed(3)}
                      </div>
                      <div className="text-xs text-gray-600">OBP</div>
                    </div>
                    <div className="text-center">
                      <div className="text-lg font-bold text-gray-900">
                        {comp.latest_stats.batting.slg.toFixed(3)}
                      </div>
                      <div className="text-xs text-gray-600">SLG</div>
                    </div>
                    <div className="text-center">
                      <div className="text-lg font-bold text-gray-900">
                        {comp.latest_stats.batting.ops.toFixed(3)}
                      </div>
                      <div className="text-xs text-gray-600">OPS</div>
                    </div>
                  </>
                )}
              </div>

              <div className="mt-3 flex flex-wrap gap-1">
                {comp.matching_features.map((feature, i) => (
                  <Badge key={i} variant="outline" className="text-xs">
                    {feature.replace('_', ' ')}
                  </Badge>
                ))}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Historical Comparisons */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <TrendingUp className="h-5 w-5" />
            <span>Historical MLB Comparisons</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {mockComparisons.historical_comparisons.map((comp, index) => (
            <div key={index} className="border border-gray-200 rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h4 className="font-semibold text-gray-900">
                    {comp.player_name}
                  </h4>
                  <p className="text-sm text-gray-600">
                    Age {comp.age_at_similar_level} comparison
                  </p>
                </div>
                <Badge variant="secondary">
                  {(comp.similarity_score * 100).toFixed(1)}% Similar
                </Badge>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <h5 className="font-medium text-gray-900 mb-2">
                    Minor League Stats
                  </h5>
                  <div className="space-y-1 text-sm">
                    <div className="flex justify-between">
                      <span>AVG:</span>
                      <span>
                        {comp.minor_league_stats_at_age.avg.toFixed(3)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>OBP:</span>
                      <span>
                        {comp.minor_league_stats_at_age.obp.toFixed(3)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>SLG:</span>
                      <span>
                        {comp.minor_league_stats_at_age.slg.toFixed(3)}
                      </span>
                    </div>
                  </div>
                </div>
                <div>
                  <h5 className="font-medium text-gray-900 mb-2">
                    MLB Outcome
                  </h5>
                  <div className="space-y-1 text-sm">
                    <div className="flex justify-between">
                      <span>Career WAR:</span>
                      <span className="font-semibold">
                        {comp.mlb_outcome.peak_war.toFixed(1)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>All-Stars:</span>
                      <span>{comp.mlb_outcome.all_star_appearances}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Career OPS:</span>
                      <span>{comp.mlb_outcome.career_ops.toFixed(3)}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function HistoryTab({ prospect }: { prospect: ProspectProfileType }) {
  return (
    <div className="space-y-6">
      {/* Career Timeline */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <Calendar className="h-5 w-5" />
            <span>Career Timeline</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex items-center space-x-4">
              <div className="flex-shrink-0 w-20 text-sm text-gray-600">
                2024
              </div>
              <div className="flex-1 border-l-2 border-blue-500 pl-4">
                <div className="font-medium">Current Season</div>
                <div className="text-sm text-gray-600">
                  {prospect.level} • {prospect.organization}
                </div>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <div className="flex-shrink-0 w-20 text-sm text-gray-600">
                2023
              </div>
              <div className="flex-1 border-l-2 border-gray-300 pl-4">
                <div className="font-medium">Previous Season</div>
                <div className="text-sm text-gray-600">
                  A+ • Level promoted mid-season
                </div>
              </div>
            </div>
            {prospect.draft_year && (
              <div className="flex items-center space-x-4">
                <div className="flex-shrink-0 w-20 text-sm text-gray-600">
                  {prospect.draft_year}
                </div>
                <div className="flex-1 border-l-2 border-green-500 pl-4">
                  <div className="font-medium">Draft Year</div>
                  <div className="text-sm text-gray-600">
                    Round {prospect.draft_round}, Pick {prospect.draft_pick}
                  </div>
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Injury History */}
      <Card>
        <CardHeader>
          <CardTitle>Injury History</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8">
            <div className="text-green-600 mb-2">
              <svg
                className="mx-auto h-12 w-12"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
            </div>
            <h3 className="text-lg font-medium text-gray-900 mb-1">
              Clean Bill of Health
            </h3>
            <p className="text-gray-600">No significant injuries reported</p>
          </div>
        </CardContent>
      </Card>

      {/* Development Notes */}
      <Card>
        <CardHeader>
          <CardTitle>Development Notes</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <div className="text-sm">
              <span className="font-medium text-gray-900">
                Promoted to {prospect.level}
              </span>
              <span className="text-gray-600 ml-2">• Mid-2024</span>
            </div>
            <div className="text-sm">
              <span className="font-medium text-gray-900">
                Added to Top 100 Prospect List
              </span>
              <span className="text-gray-600 ml-2">• Early 2024</span>
            </div>
            <div className="text-sm">
              <span className="font-medium text-gray-900">
                Breakout Performance
              </span>
              <span className="text-gray-600 ml-2">• 2023 Season</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default function ProspectProfile({ id }: ProspectProfileProps) {
  const [activeTab, setActiveTab] = useState('overview');
  const { data: prospect, loading, error, refetch } = useProspectProfile(id);

  const tabs = [
    { id: 'overview', name: 'Overview' },
    {
      id: 'statistics',
      name: 'Statistics',
      count: prospect?.stats?.length || 0,
    },
    { id: 'scouting', name: 'Scouting' },
    { id: 'comparisons', name: 'Comparisons' },
    { id: 'history', name: 'History' },
  ];

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="flex justify-center py-12">
          <LoadingSpinner size="lg" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto px-4 py-8">
        <ErrorMessage message={error} onRetry={refetch} className="max-w-md" />
      </div>
    );
  }

  if (!prospect) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="text-center py-12">
          <h2 className="text-2xl font-bold text-gray-900">
            Prospect not found
          </h2>
          <p className="mt-2 text-gray-600">
            The prospect you&apos;re looking for doesn&apos;t exist.
          </p>
          <Link
            href="/prospects"
            className="mt-4 inline-flex items-center rounded-md bg-blue-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-500"
          >
            Back to Rankings
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 bg-gray-50 min-h-screen">
      {/* Back Navigation */}
      <div className="mb-6 flex items-center justify-between">
        <Link
          href="/"
          className="flex items-center text-gray-600 hover:text-gray-900 transition-colors"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Rankings
        </Link>
        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm">
            <Star className="h-4 w-4 mr-2" />
            Add to Watchlist
          </Button>
          <Button variant="default" size="sm" className="bg-gradient-to-r from-yellow-400 to-orange-500 hover:from-yellow-500 hover:to-orange-600">
            <TrendingUp className="h-4 w-4 mr-2" />
            Upgrade
          </Button>
        </div>
      </div>

      {/* Prospect Header with ML Prediction - Side by Side */}
      <div className="mb-8 grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Prospect Header Card */}
        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <div className="flex items-start space-x-6">
            {/* Prospect Photo */}
            <div className="flex-shrink-0">
              <div className="h-32 w-32 rounded-lg bg-gradient-to-br from-blue-400 to-blue-600 flex items-center justify-center">
                <svg
                  className="h-16 w-16 text-white"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                  />
                </svg>
              </div>
            </div>
            {/* Prospect Info */}
            <div className="flex-1 min-w-0">
              <h1 className="text-3xl font-bold text-gray-900 mb-3">
                {prospect.name}
              </h1>
              <div className="space-y-2">
                <div className="flex items-center text-sm">
                  <span className="font-semibold text-blue-600 text-lg">
                    {prospect.position}
                  </span>
                  <span className="mx-2 text-gray-400">|</span>
                  <span className="text-gray-700">{prospect.organization}</span>
                </div>
                <div className="flex items-center text-sm text-gray-600">
                  <span>Age {prospect.age}</span>
                  <span className="mx-2">|</span>
                  <span>ETA {prospect.eta_year || 'TBD'}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ML Prediction Card */}
        <MLPredictionCard prediction={prospect.ml_prediction} />
      </div>

      {/* Tabs Navigation */}
      <div className="mb-6">
        <Tabs activeTab={activeTab} onTabChange={setActiveTab} tabs={tabs} />
      </div>

      {/* Tab Content */}
      <div className="min-h-96">
        {activeTab === 'overview' && <OverviewTab prospect={prospect} />}
        {activeTab === 'statistics' && <StatisticsTab prospect={prospect} />}
        {activeTab === 'scouting' && <ScoutingTab prospect={prospect} />}
        {activeTab === 'comparisons' && <ComparisonsTab prospect={prospect} />}
        {activeTab === 'history' && <HistoryTab prospect={prospect} />}
      </div>
    </div>
  );
}
