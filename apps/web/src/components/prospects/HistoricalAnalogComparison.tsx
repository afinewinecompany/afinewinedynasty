'use client';

import { useState } from 'react';
import {
  Clock,
  Star,
  TrendingUp,
  Award,
  Info,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import { ComparisonProspect } from '@/types/prospect';

interface HistoricalAnalogComparisonProps {
  comparisonData: {
    prospects?: ComparisonProspect[];
    historical_analogs?: {
      prospect_analogs?: Record<string, { analogs: HistoricalAnalog[] }>;
      common_analog_patterns?: string[];
      comparative_insights?: string;
    };
  };
  selectedProspects: ComparisonProspect[];
}

interface AnalogOutcome {
  reached_mlb: boolean;
  peak_war?: number;
  all_star_appearances?: number;
  career_ops?: number;
  cy_young_awards?: number;
  career_era?: number;
}

interface HistoricalAnalog {
  player_name: string;
  similarity_score: number;
  age_at_similar_level: number;
  mlb_outcome: AnalogOutcome;
  minor_league_stats_at_age: {
    era?: number;
    whip?: number;
    k_9?: number;
    avg?: number;
    obp?: number;
    slg?: number;
  };
}

const OUTCOME_COLORS = {
  elite: 'bg-green-100 text-green-800 border-green-200',
  good: 'bg-blue-100 text-blue-800 border-blue-200',
  average: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  poor: 'bg-red-100 text-red-800 border-red-200',
};

export default function HistoricalAnalogComparison({
  comparisonData,
}: HistoricalAnalogComparisonProps) {
  const [expandedAnalogs, setExpandedAnalogs] = useState(true);
  const [selectedProspectIndex, setSelectedProspectIndex] = useState(0);

  const prospects = comparisonData?.prospects || [];
  const analogsData = comparisonData?.historical_analogs || {};

  const categorizeOutcome = (
    outcome: AnalogOutcome,
    position: string
  ): string => {
    if (!outcome.reached_mlb) return 'poor';

    const isPitcher = position === 'SP' || position === 'RP';

    if (isPitcher) {
      if (outcome.cy_young_awards && outcome.cy_young_awards > 0)
        return 'elite';
      if (outcome.peak_war && outcome.peak_war > 15) return 'elite';
      if (outcome.peak_war && outcome.peak_war > 8) return 'good';
      if (outcome.peak_war && outcome.peak_war > 3) return 'average';
      return 'poor';
    } else {
      if (outcome.peak_war && outcome.peak_war > 25) return 'elite';
      if (outcome.all_star_appearances && outcome.all_star_appearances > 3)
        return 'elite';
      if (outcome.peak_war && outcome.peak_war > 15) return 'good';
      if (outcome.peak_war && outcome.peak_war > 5) return 'average';
      return 'poor';
    }
  };

  const getOutcomeDescription = (category: string): string => {
    switch (category) {
      case 'elite':
        return 'Star/Superstar';
      case 'good':
        return 'Solid Contributor';
      case 'average':
        return 'Role Player';
      case 'poor':
        return 'Fringe/Failed';
      default:
        return 'Unknown';
    }
  };

  const formatStat = (
    value: number | undefined,
    format: 'avg' | 'era' | 'ops' | 'war' | 'count'
  ): string => {
    if (value === undefined || value === null) return 'N/A';

    switch (format) {
      case 'avg':
      case 'ops':
        return value.toFixed(3);
      case 'era':
        return value.toFixed(2);
      case 'war':
        return value.toFixed(1);
      case 'count':
        return value.toString();
      default:
        return value.toString();
    }
  };

  if (prospects.length === 0) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
        <div className="flex items-center gap-3">
          <Info className="w-5 h-5 text-yellow-600" />
          <div>
            <h3 className="font-medium text-yellow-800">
              No Analog Data Available
            </h3>
            <p className="text-sm text-yellow-700 mt-1">
              Historical analog comparison requires prospect data.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Historical Analogs */}
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <button
          onClick={() => setExpandedAnalogs(!expandedAnalogs)}
          className="w-full flex items-center justify-between p-4 bg-orange-50 hover:bg-orange-100 transition-colors"
        >
          <h3 className="font-semibold text-orange-900 flex items-center gap-2">
            <Clock className="w-5 h-5" />
            Historical Analog Comparison
          </h3>
          {expandedAnalogs ? (
            <ChevronDown className="w-5 h-5 text-orange-600" />
          ) : (
            <ChevronRight className="w-5 h-5 text-orange-600" />
          )}
        </button>

        {expandedAnalogs && (
          <div className="p-6">
            {/* Prospect Selector */}
            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 mb-3">
                Select Prospect for Analog Analysis
              </label>
              <div className="flex flex-wrap gap-2">
                {prospects.map((prospect, index) => (
                  <button
                    key={prospect.id}
                    onClick={() => setSelectedProspectIndex(index)}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                      selectedProspectIndex === index
                        ? 'bg-orange-100 text-orange-800 border-2 border-orange-300'
                        : 'bg-gray-100 text-gray-700 border-2 border-gray-200 hover:bg-gray-200'
                    }`}
                  >
                    {prospect.name}
                    <span className="ml-2 text-xs opacity-75">
                      {prospect.position} • {prospect.organization}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            {(() => {
              const selectedProspect = prospects[selectedProspectIndex];
              if (!selectedProspect) return null;

              // Get analogs for selected prospect
              const prospectAnalogs =
                analogsData.prospect_analogs?.[selectedProspect.id]?.analogs ||
                [];

              if (prospectAnalogs.length === 0) {
                return (
                  <div className="text-center py-8 text-gray-500">
                    <Clock className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                    <p>
                      No historical analogs found for {selectedProspect.name}
                    </p>
                    <p className="text-sm mt-1">
                      This may indicate a unique prospect profile or
                      insufficient historical data.
                    </p>
                  </div>
                );
              }

              return (
                <div className="space-y-6">
                  {/* Selected Prospect Info */}
                  <div className="bg-orange-50 rounded-lg p-4">
                    <h4 className="font-semibold text-orange-900 mb-2">
                      Historical Analogs for {selectedProspect.name}
                    </h4>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                      <div>
                        <span className="text-orange-700 font-medium">
                          Position:
                        </span>
                        <span className="ml-2">
                          {selectedProspect.position}
                        </span>
                      </div>
                      <div>
                        <span className="text-orange-700 font-medium">
                          Age:
                        </span>
                        <span className="ml-2">{selectedProspect.age}</span>
                      </div>
                      <div>
                        <span className="text-orange-700 font-medium">
                          Level:
                        </span>
                        <span className="ml-2">{selectedProspect.level}</span>
                      </div>
                      <div>
                        <span className="text-orange-700 font-medium">
                          ETA:
                        </span>
                        <span className="ml-2">
                          {selectedProspect.eta_year || 'TBD'}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Historical Analogs List */}
                  <div className="space-y-4">
                    {prospectAnalogs.map(
                      (analog: HistoricalAnalog, index: number) => {
                        const outcomeCategory = categorizeOutcome(
                          analog.mlb_outcome,
                          selectedProspect.position
                        );
                        const isPitcher =
                          selectedProspect.position === 'SP' ||
                          selectedProspect.position === 'RP';

                        return (
                          <div
                            key={index}
                            className="border border-gray-200 rounded-lg p-6"
                          >
                            <div className="flex items-start justify-between mb-4">
                              <div>
                                <h5 className="text-lg font-semibold text-gray-900">
                                  {analog.player_name}
                                </h5>
                                <div className="flex items-center gap-4 mt-1 text-sm text-gray-600">
                                  <span>
                                    Similarity:{' '}
                                    {(analog.similarity_score * 100).toFixed(1)}
                                    %
                                  </span>
                                  <span>
                                    Age at level: {analog.age_at_similar_level}
                                  </span>
                                </div>
                              </div>
                              <div
                                className={`px-3 py-1 rounded-full text-sm font-medium border ${OUTCOME_COLORS[outcomeCategory]}`}
                              >
                                {getOutcomeDescription(outcomeCategory)}
                              </div>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                              {/* MLB Career Outcome */}
                              <div>
                                <h6 className="font-medium text-gray-900 mb-3 flex items-center gap-2">
                                  <Award className="w-4 h-4 text-yellow-600" />
                                  MLB Career Outcome
                                </h6>
                                <div className="space-y-2 text-sm">
                                  <div className="flex justify-between">
                                    <span className="text-gray-600">
                                      Reached MLB:
                                    </span>
                                    <span
                                      className={`font-medium ${
                                        analog.mlb_outcome.reached_mlb
                                          ? 'text-green-600'
                                          : 'text-red-600'
                                      }`}
                                    >
                                      {analog.mlb_outcome.reached_mlb
                                        ? 'Yes'
                                        : 'No'}
                                    </span>
                                  </div>

                                  {analog.mlb_outcome.reached_mlb && (
                                    <>
                                      <div className="flex justify-between">
                                        <span className="text-gray-600">
                                          Peak WAR:
                                        </span>
                                        <span className="font-medium">
                                          {formatStat(
                                            analog.mlb_outcome.peak_war,
                                            'war'
                                          )}
                                        </span>
                                      </div>

                                      {isPitcher ? (
                                        <>
                                          <div className="flex justify-between">
                                            <span className="text-gray-600">
                                              Career ERA:
                                            </span>
                                            <span className="font-medium">
                                              {formatStat(
                                                analog.mlb_outcome.career_era,
                                                'era'
                                              )}
                                            </span>
                                          </div>
                                          <div className="flex justify-between">
                                            <span className="text-gray-600">
                                              Cy Young Awards:
                                            </span>
                                            <span className="font-medium">
                                              {formatStat(
                                                analog.mlb_outcome
                                                  .cy_young_awards,
                                                'count'
                                              )}
                                            </span>
                                          </div>
                                        </>
                                      ) : (
                                        <>
                                          <div className="flex justify-between">
                                            <span className="text-gray-600">
                                              Career OPS:
                                            </span>
                                            <span className="font-medium">
                                              {formatStat(
                                                analog.mlb_outcome.career_ops,
                                                'ops'
                                              )}
                                            </span>
                                          </div>
                                          <div className="flex justify-between">
                                            <span className="text-gray-600">
                                              All-Star Games:
                                            </span>
                                            <span className="font-medium">
                                              {formatStat(
                                                analog.mlb_outcome
                                                  .all_star_appearances,
                                                'count'
                                              )}
                                            </span>
                                          </div>
                                        </>
                                      )}
                                    </>
                                  )}
                                </div>
                              </div>

                              {/* Minor League Stats at Similar Age */}
                              <div>
                                <h6 className="font-medium text-gray-900 mb-3 flex items-center gap-2">
                                  <Star className="w-4 h-4 text-blue-600" />
                                  Minor League Stats at Age{' '}
                                  {analog.age_at_similar_level}
                                </h6>
                                <div className="space-y-2 text-sm">
                                  {isPitcher ? (
                                    <>
                                      <div className="flex justify-between">
                                        <span className="text-gray-600">
                                          ERA:
                                        </span>
                                        <span className="font-medium">
                                          {formatStat(
                                            analog.minor_league_stats_at_age
                                              ?.era,
                                            'era'
                                          )}
                                        </span>
                                      </div>
                                      <div className="flex justify-between">
                                        <span className="text-gray-600">
                                          WHIP:
                                        </span>
                                        <span className="font-medium">
                                          {formatStat(
                                            analog.minor_league_stats_at_age
                                              ?.whip,
                                            'era'
                                          )}
                                        </span>
                                      </div>
                                      <div className="flex justify-between">
                                        <span className="text-gray-600">
                                          K/9:
                                        </span>
                                        <span className="font-medium">
                                          {formatStat(
                                            analog.minor_league_stats_at_age
                                              ?.k_9,
                                            'war'
                                          )}
                                        </span>
                                      </div>
                                    </>
                                  ) : (
                                    <>
                                      <div className="flex justify-between">
                                        <span className="text-gray-600">
                                          Batting Avg:
                                        </span>
                                        <span className="font-medium">
                                          {formatStat(
                                            analog.minor_league_stats_at_age
                                              ?.avg,
                                            'avg'
                                          )}
                                        </span>
                                      </div>
                                      <div className="flex justify-between">
                                        <span className="text-gray-600">
                                          OBP:
                                        </span>
                                        <span className="font-medium">
                                          {formatStat(
                                            analog.minor_league_stats_at_age
                                              ?.obp,
                                            'avg'
                                          )}
                                        </span>
                                      </div>
                                      <div className="flex justify-between">
                                        <span className="text-gray-600">
                                          SLG:
                                        </span>
                                        <span className="font-medium">
                                          {formatStat(
                                            analog.minor_league_stats_at_age
                                              ?.slg,
                                            'avg'
                                          )}
                                        </span>
                                      </div>
                                    </>
                                  )}
                                </div>
                              </div>
                            </div>

                            {/* Similarity Factors */}
                            <div className="mt-4 p-3 bg-gray-50 rounded-lg">
                              <p className="text-xs text-gray-600">
                                <strong>Similarity factors:</strong>{' '}
                                Age-adjusted performance metrics, level
                                progression rate, physical profile, and
                                position-specific skills. Higher similarity
                                scores indicate more comparable development
                                patterns.
                              </p>
                            </div>
                          </div>
                        );
                      }
                    )}
                  </div>

                  {/* Outcome Distribution */}
                  <div className="bg-gray-50 rounded-lg p-4">
                    <h4 className="font-semibold text-gray-900 mb-3">
                      Analog Outcome Summary
                    </h4>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      {Object.keys(OUTCOME_COLORS).map((category) => {
                        const count = prospectAnalogs.filter(
                          (analog) =>
                            categorizeOutcome(
                              analog.mlb_outcome,
                              selectedProspect.position
                            ) === category
                        ).length;

                        const percentage =
                          prospectAnalogs.length > 0
                            ? ((count / prospectAnalogs.length) * 100).toFixed(
                                0
                              )
                            : 0;

                        return (
                          <div key={category} className="text-center">
                            <div
                              className={`text-2xl font-bold mb-1 ${OUTCOME_COLORS[category].split(' ')[1]}`}
                            >
                              {count}
                            </div>
                            <div className="text-sm font-medium text-gray-900">
                              {getOutcomeDescription(category)}
                            </div>
                            <div className="text-xs text-gray-500">
                              {percentage}% of analogs
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              );
            })()}
          </div>
        )}
      </div>

      {/* Comparative Analog Insights */}
      {analogsData.common_analog_patterns &&
        analogsData.common_analog_patterns.length > 0 && (
          <div className="bg-white border border-gray-200 rounded-lg p-6">
            <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-green-600" />
              Cross-Prospect Analog Patterns
            </h3>

            <div className="space-y-4">
              <div>
                <h4 className="font-medium text-gray-800 mb-2">
                  Common Historical Comparisons
                </h4>
                <div className="flex flex-wrap gap-2">
                  {analogsData.common_analog_patterns.map(
                    (player: string, index: number) => (
                      <span
                        key={index}
                        className="px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm font-medium"
                      >
                        {player}
                      </span>
                    )
                  )}
                </div>
              </div>

              <div className="p-3 bg-blue-50 rounded-lg">
                <p className="text-sm text-blue-800">
                  <strong>Insight:</strong> {analogsData.comparative_insights}
                  {analogsData.common_analog_patterns.length > 0 &&
                    ' Multiple prospects sharing similar historical profiles may indicate similar development pathways and potential outcomes.'}
                </p>
              </div>
            </div>
          </div>
        )}
    </div>
  );
}
