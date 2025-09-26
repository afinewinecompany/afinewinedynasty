'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useProspectProfile } from '@/hooks/useProspectProfile';
import { ProspectProfile as ProspectProfileType } from '@/types/prospect';
import LoadingSpinner from '@/components/ui/LoadingSpinner';
import ErrorMessage from '@/components/ui/ErrorMessage';

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
      <h3 className="text-lg font-medium text-gray-900 mb-4">ML Prediction</h3>
      <div className="space-y-4">
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-gray-600">Success Probability</span>
            <span
              className={`text-2xl font-bold ${getProbabilityColor(
                prediction.success_probability
              )}`}
            >
              {Math.round(prediction.success_probability * 100)}%
            </span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className={`h-2 rounded-full ${
                prediction.success_probability >= 0.7
                  ? 'bg-green-500'
                  : prediction.success_probability >= 0.4
                    ? 'bg-yellow-500'
                    : 'bg-red-500'
              }`}
              style={{ width: `${prediction.success_probability * 100}%` }}
            />
          </div>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-600">Confidence Level</span>
          <span
            className={`inline-flex rounded-full px-2 text-xs font-semibold leading-5 ${getConfidenceColor(
              prediction.confidence_level
            )}`}
          >
            {prediction.confidence_level}
          </span>
        </div>
        {prediction.explanation && (
          <div>
            <span className="text-sm text-gray-600 block mb-2">Analysis</span>
            <p className="text-sm text-gray-800">{prediction.explanation}</p>
          </div>
        )}
        <div className="text-xs text-gray-500">
          Generated on {new Date(prediction.generated_at).toLocaleDateString()}
        </div>
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
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="space-y-4">
          <div className="rounded-lg border border-gray-200 bg-white p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">
              Basic Information
            </h3>
            <dl className="space-y-3">
              <div className="flex justify-between">
                <dt className="text-sm text-gray-600">Position</dt>
                <dd className="text-sm font-medium text-gray-900">
                  {prospect.position}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-sm text-gray-600">Organization</dt>
                <dd className="text-sm font-medium text-gray-900">
                  {prospect.organization}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-sm text-gray-600">Level</dt>
                <dd className="text-sm font-medium text-gray-900">
                  {prospect.level}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-sm text-gray-600">Age</dt>
                <dd className="text-sm font-medium text-gray-900">
                  {prospect.age}
                </dd>
              </div>
              {prospect.eta_year && (
                <div className="flex justify-between">
                  <dt className="text-sm text-gray-600">ETA Year</dt>
                  <dd className="text-sm font-medium text-gray-900">
                    {prospect.eta_year}
                  </dd>
                </div>
              )}
              {prospect.scouting_grade && (
                <div className="flex justify-between">
                  <dt className="text-sm text-gray-600">Scouting Grade</dt>
                  <dd className="text-sm font-medium text-gray-900">
                    {prospect.scouting_grade}/100
                  </dd>
                </div>
              )}
            </dl>
          </div>
        </div>

        <MLPredictionCard prediction={prospect.ml_prediction} />
      </div>
    </div>
  );
}

interface StatisticsTabProps {
  stats?: ProspectProfileType['stats'];
}

function StatisticsTab({ stats }: StatisticsTabProps) {
  if (!stats || stats.length === 0) {
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

  const latestStats = stats[stats.length - 1];

  const isHitter =
    latestStats.at_bats !== undefined || latestStats.batting_avg !== undefined;
  const isPitcher =
    latestStats.innings_pitched !== undefined || latestStats.era !== undefined;

  return (
    <div className="space-y-6">
      {isHitter && (
        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">
            Hitting Statistics
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {latestStats.games_played && (
              <div className="text-center">
                <div className="text-2xl font-bold text-gray-900">
                  {latestStats.games_played}
                </div>
                <div className="text-sm text-gray-600">Games</div>
              </div>
            )}
            {latestStats.at_bats && (
              <div className="text-center">
                <div className="text-2xl font-bold text-gray-900">
                  {latestStats.at_bats}
                </div>
                <div className="text-sm text-gray-600">At Bats</div>
              </div>
            )}
            {latestStats.hits && (
              <div className="text-center">
                <div className="text-2xl font-bold text-gray-900">
                  {latestStats.hits}
                </div>
                <div className="text-sm text-gray-600">Hits</div>
              </div>
            )}
            {latestStats.home_runs && (
              <div className="text-center">
                <div className="text-2xl font-bold text-gray-900">
                  {latestStats.home_runs}
                </div>
                <div className="text-sm text-gray-600">Home Runs</div>
              </div>
            )}
            {latestStats.rbi && (
              <div className="text-center">
                <div className="text-2xl font-bold text-gray-900">
                  {latestStats.rbi}
                </div>
                <div className="text-sm text-gray-600">RBI</div>
              </div>
            )}
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
          </div>
        </div>
      )}

      {isPitcher && (
        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">
            Pitching Statistics
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {latestStats.innings_pitched && (
              <div className="text-center">
                <div className="text-2xl font-bold text-gray-900">
                  {latestStats.innings_pitched.toFixed(1)}
                </div>
                <div className="text-sm text-gray-600">IP</div>
              </div>
            )}
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
          </div>
        </div>
      )}

      {(latestStats.woba || latestStats.wrc_plus) && (
        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">
            Advanced Metrics
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {latestStats.woba && (
              <div className="text-center">
                <div className="text-2xl font-bold text-gray-900">
                  {latestStats.woba.toFixed(3)}
                </div>
                <div className="text-sm text-gray-600">wOBA</div>
              </div>
            )}
            {latestStats.wrc_plus && (
              <div className="text-center">
                <div className="text-2xl font-bold text-gray-900">
                  {latestStats.wrc_plus}
                </div>
                <div className="text-sm text-gray-600">wRC+</div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function ScoutingTab() {
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
          d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
        />
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
        />
      </svg>
      <h3 className="mt-2 text-sm font-medium text-gray-900">
        Scouting report coming soon
      </h3>
      <p className="mt-1 text-sm text-gray-500">
        Detailed scouting grades and reports will be available here.
      </p>
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
    <div className="container mx-auto px-4 py-8">
      {/* Breadcrumb Navigation */}
      <nav className="mb-6" aria-label="Breadcrumb">
        <ol className="flex items-center space-x-2 text-sm">
          <li>
            <Link
              href="/prospects"
              className="text-gray-500 hover:text-gray-700"
            >
              Prospect Rankings
            </Link>
          </li>
          <li>
            <svg
              className="h-4 w-4 text-gray-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 5l7 7-7 7"
              />
            </svg>
          </li>
          <li className="text-gray-900 font-medium">{prospect.name}</li>
        </ol>
      </nav>

      {/* Prospect Header */}
      <div className="mb-8 rounded-lg border border-gray-200 bg-white p-6">
        <div className="flex items-start space-x-6">
          {/* Placeholder for prospect photo */}
          <div className="flex-shrink-0">
            <div className="h-24 w-24 rounded-lg bg-gray-200 flex items-center justify-center">
              <svg
                className="h-12 w-12 text-gray-400"
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
          <div className="flex-1 min-w-0">
            <h1 className="text-3xl font-bold text-gray-900 mb-2">
              {prospect.name}
            </h1>
            <div className="flex flex-wrap items-center space-x-4 text-sm text-gray-600">
              <span className="font-medium text-blue-600">
                {prospect.position}
              </span>
              <span>•</span>
              <span>{prospect.organization}</span>
              <span>•</span>
              <span>{prospect.level}</span>
              <span>•</span>
              <span>Age {prospect.age}</span>
              {prospect.eta_year && (
                <>
                  <span>•</span>
                  <span>ETA {prospect.eta_year}</span>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Tabs Navigation */}
      <div className="mb-6">
        <Tabs activeTab={activeTab} onTabChange={setActiveTab} tabs={tabs} />
      </div>

      {/* Tab Content */}
      <div className="min-h-96">
        {activeTab === 'overview' && <OverviewTab prospect={prospect} />}
        {activeTab === 'statistics' && <StatisticsTab stats={prospect.stats} />}
        {activeTab === 'scouting' && <ScoutingTab />}
      </div>
    </div>
  );
}
