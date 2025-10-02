'use client';

import { useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import {
  TrendingUp,
  TrendingDown,
  Info,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import { ComparisonProspect } from '@/types/prospect';

interface MLPredictionComparisonProps {
  comparisonData: {
    prospects?: ComparisonProspect[];
    ml_comparison?: {
      prediction_comparison?: Array<{
        prospect_a: { name: string; probability: number };
        prospect_b: { name: string; probability: number };
        probability_difference: number;
        significance: string;
        advantage: string;
        key_differentiators?: Array<{
          feature: string;
          difference: number;
          favors: string;
        }>;
      }>;
    };
  };
  selectedProspects: ComparisonProspect[];
}

interface ShapFeature {
  feature: string;
  difference: number;
  favors: string;
}

const CONFIDENCE_COLORS = {
  High: '#10b981',
  Medium: '#f59e0b',
  Low: '#ef4444',
};

const SHAP_FEATURE_LABELS = {
  age: 'Age',
  level: 'Minor League Level',
  batting_avg: 'Batting Average',
  on_base_pct: 'On-Base Percentage',
  slugging_pct: 'Slugging Percentage',
  wrc_plus: 'wRC+',
  strikeout_rate: 'Strikeout Rate',
  walk_rate: 'Walk Rate',
  era: 'ERA',
  whip: 'WHIP',
  k_per_9: 'K/9',
  bb_per_9: 'BB/9',
  overall_grade: 'Overall Scouting Grade',
  future_value: 'Future Value Grade',
  speed: 'Speed Tool',
  power: 'Power Tool',
  hit: 'Hit Tool',
  field: 'Field Tool',
  arm: 'Arm Tool',
};

export default function MLPredictionComparison({
  comparisonData,
}: MLPredictionComparisonProps) {
  const [expandedPredictions, setExpandedPredictions] = useState(true);
  const [expandedShap, setExpandedShap] = useState(false);
  const [selectedComparison, setSelectedComparison] = useState(0);

  const prospects = comparisonData?.prospects || [];
  const mlComparison = comparisonData?.ml_comparison || {};

  // Filter prospects that have ML predictions
  const prospectsWithML = prospects.filter((p) => p.ml_prediction);

  if (prospectsWithML.length < 2) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
        <div className="flex items-center gap-3">
          <Info className="w-5 h-5 text-yellow-600" />
          <div>
            <h3 className="font-medium text-yellow-800">
              Limited ML Prediction Data
            </h3>
            <p className="text-sm text-yellow-700 mt-1">
              At least 2 prospects with ML predictions are required for
              comparison analysis.
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Prepare prediction comparison data for chart
  const predictionData = prospectsWithML.map((prospect) => ({
    name: prospect.name,
    probability: (prospect.ml_prediction.success_probability * 100).toFixed(1),
    confidence: prospect.ml_prediction.confidence_level,
    rawProbability: prospect.ml_prediction.success_probability,
  }));

  // Get comparison pairs
  const comparisonPairs = mlComparison.prediction_comparison || [];

  const getConfidenceColor = (confidence: string) => {
    return CONFIDENCE_COLORS[confidence] || '#6b7280';
  };

  const getPredictionIcon = (probability: number) => {
    if (probability >= 0.7)
      return <TrendingUp className="w-4 h-4 text-green-600" />;
    if (probability >= 0.4)
      return <TrendingUp className="w-4 h-4 text-yellow-600" />;
    return <TrendingDown className="w-4 h-4 text-red-600" />;
  };

  const getShapDifferentials = (comparison: {
    key_differentiators?: Array<{
      feature: string;
      difference: number;
      favors: string;
    }>;
  }): ShapFeature[] => {
    return (comparison.key_differentiators || []).map((diff) => ({
      feature: SHAP_FEATURE_LABELS[diff.feature] || diff.feature,
      difference: Math.abs(diff.difference),
      favors: diff.favors,
    }));
  };

  return (
    <div className="space-y-6">
      {/* ML Prediction Overview */}
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <button
          onClick={() => setExpandedPredictions(!expandedPredictions)}
          className="w-full flex items-center justify-between p-4 bg-blue-50 hover:bg-blue-100 transition-colors"
        >
          <h3 className="font-semibold text-blue-900">
            ML Prediction Comparison
          </h3>
          {expandedPredictions ? (
            <ChevronDown className="w-5 h-5 text-blue-600" />
          ) : (
            <ChevronRight className="w-5 h-5 text-blue-600" />
          )}
        </button>

        {expandedPredictions && (
          <div className="p-6">
            {/* Prediction Chart */}
            <div className="mb-6">
              <h4 className="font-medium text-gray-900 mb-4">
                Success Probability Comparison
              </h4>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={predictionData}
                    margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="name"
                      tick={{ fontSize: 12 }}
                      interval={0}
                      angle={-45}
                      textAnchor="end"
                      height={80}
                    />
                    <YAxis
                      domain={[0, 100]}
                      tick={{ fontSize: 12 }}
                      label={{
                        value: 'Success Probability (%)',
                        angle: -90,
                        position: 'insideLeft',
                      }}
                    />
                    <Tooltip
                      formatter={(value) => [
                        `${value}%`,
                        'Success Probability',
                      ]}
                      labelFormatter={(label) => `Prospect: ${label}`}
                      contentStyle={{
                        backgroundColor: '#f9fafb',
                        border: '1px solid #e5e7eb',
                        borderRadius: '6px',
                      }}
                    />
                    <Bar dataKey="probability" radius={[4, 4, 0, 0]}>
                      {predictionData.map((entry, index) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={getConfidenceColor(entry.confidence)}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Prediction Details Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {prospectsWithML.map((prospect) => {
                const prediction = prospect.ml_prediction;
                return (
                  <div key={prospect.id} className="bg-gray-50 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-3">
                      <h5 className="font-medium text-gray-900">
                        {prospect.name}
                      </h5>
                      {getPredictionIcon(prediction.success_probability)}
                    </div>

                    <div className="space-y-2">
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-gray-600">
                          Success Probability
                        </span>
                        <span className="font-semibold text-gray-900">
                          {(prediction.success_probability * 100).toFixed(1)}%
                        </span>
                      </div>

                      <div className="flex justify-between items-center">
                        <span className="text-sm text-gray-600">
                          Confidence
                        </span>
                        <span
                          className="inline-flex px-2 py-1 text-xs font-medium rounded-full"
                          style={{
                            backgroundColor: `${getConfidenceColor(prediction.confidence_level)}20`,
                            color: getConfidenceColor(
                              prediction.confidence_level
                            ),
                          }}
                        >
                          {prediction.confidence_level}
                        </span>
                      </div>

                      <div className="w-full bg-gray-200 rounded-full h-2 mt-3">
                        <div
                          className="h-2 rounded-full transition-all duration-300"
                          style={{
                            width: `${prediction.success_probability * 100}%`,
                            backgroundColor: getConfidenceColor(
                              prediction.confidence_level
                            ),
                          }}
                        />
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* SHAP Value Differential Analysis */}
      {comparisonPairs.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <button
            onClick={() => setExpandedShap(!expandedShap)}
            className="w-full flex items-center justify-between p-4 bg-purple-50 hover:bg-purple-100 transition-colors"
          >
            <h3 className="font-semibold text-purple-900">
              SHAP Feature Differential Analysis
            </h3>
            {expandedShap ? (
              <ChevronDown className="w-5 h-5 text-purple-600" />
            ) : (
              <ChevronRight className="w-5 h-5 text-purple-600" />
            )}
          </button>

          {expandedShap && (
            <div className="p-6">
              <div className="mb-4">
                <p className="text-sm text-gray-600 mb-4">
                  SHAP (SHapley Additive exPlanations) values show which
                  features contribute most to prediction differences between
                  prospects.
                </p>

                {/* Comparison Selector */}
                {comparisonPairs.length > 1 && (
                  <div className="mb-4">
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Select Comparison Pair
                    </label>
                    <select
                      value={selectedComparison}
                      onChange={(e) =>
                        setSelectedComparison(parseInt(e.target.value))
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                    >
                      {comparisonPairs.map((pair, index) => (
                        <option key={index} value={index}>
                          {pair.prospect_a.name} vs {pair.prospect_b.name}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>

              {comparisonPairs[selectedComparison] && (
                <div>
                  {(() => {
                    const comparison = comparisonPairs[selectedComparison];
                    const shapDiffs = getShapDifferentials(comparison);

                    return (
                      <>
                        {/* Comparison Summary */}
                        <div className="bg-gray-50 rounded-lg p-4 mb-6">
                          <div className="grid grid-cols-2 gap-4 mb-4">
                            <div className="text-center">
                              <h4 className="font-semibold text-gray-900">
                                {comparison.prospect_a.name}
                              </h4>
                              <div className="text-2xl font-bold text-purple-600 mt-1">
                                {(
                                  comparison.prospect_a.probability * 100
                                ).toFixed(1)}
                                %
                              </div>
                            </div>
                            <div className="text-center">
                              <h4 className="font-semibold text-gray-900">
                                {comparison.prospect_b.name}
                              </h4>
                              <div className="text-2xl font-bold text-purple-600 mt-1">
                                {(
                                  comparison.prospect_b.probability * 100
                                ).toFixed(1)}
                                %
                              </div>
                            </div>
                          </div>

                          <div className="text-center border-t pt-4">
                            <div className="text-sm text-gray-600">
                              Probability Difference
                            </div>
                            <div
                              className={`text-lg font-semibold ${
                                comparison.probability_difference > 0
                                  ? 'text-green-600'
                                  : 'text-red-600'
                              }`}
                            >
                              {comparison.probability_difference > 0 ? '+' : ''}
                              {(
                                comparison.probability_difference * 100
                              ).toFixed(1)}
                              %
                            </div>
                            <div className="text-xs text-gray-500 mt-1">
                              Significance: {comparison.significance}
                            </div>
                          </div>
                        </div>

                        {/* Key Differentiators */}
                        {shapDiffs.length > 0 && (
                          <div>
                            <h4 className="font-medium text-gray-900 mb-4">
                              Key Feature Differentiators
                            </h4>
                            <div className="space-y-3">
                              {shapDiffs.map((diff, index) => (
                                <div
                                  key={index}
                                  className="flex items-center justify-between p-3 bg-purple-25 rounded-lg"
                                >
                                  <div className="flex-1">
                                    <span className="font-medium text-gray-900">
                                      {diff.feature}
                                    </span>
                                  </div>
                                  <div className="flex items-center gap-3">
                                    <span className="text-sm text-gray-600">
                                      Favors:{' '}
                                      <span className="font-medium">
                                        {diff.favors}
                                      </span>
                                    </span>
                                    <div className="w-16 bg-gray-200 rounded-full h-2">
                                      <div
                                        className="h-2 bg-purple-500 rounded-full"
                                        style={{
                                          width: `${Math.min(diff.difference * 100, 100)}%`,
                                        }}
                                      />
                                    </div>
                                    <span className="text-xs text-purple-600 font-medium w-12 text-right">
                                      {diff.difference.toFixed(3)}
                                    </span>
                                  </div>
                                </div>
                              ))}
                            </div>

                            <div className="mt-4 p-3 bg-blue-50 rounded-lg">
                              <p className="text-sm text-blue-800">
                                <strong>Interpretation:</strong> Higher SHAP
                                values indicate features that contribute more
                                strongly to the prediction difference. Features
                                favoring {comparison.advantage} are the primary
                                drivers of their higher success probability.
                              </p>
                            </div>
                          </div>
                        )}
                      </>
                    );
                  })()}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Confidence Analysis */}
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <h3 className="font-semibold text-gray-900 mb-4">
          Prediction Confidence Analysis
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {Object.entries(CONFIDENCE_COLORS).map(([level, color]) => {
            const count = prospectsWithML.filter(
              (p) => p.ml_prediction.confidence_level === level
            ).length;
            const percentage = ((count / prospectsWithML.length) * 100).toFixed(
              0
            );

            return (
              <div
                key={level}
                className="text-center p-4 rounded-lg border-2"
                style={{ borderColor: color + '40' }}
              >
                <div className="text-2xl font-bold mb-1" style={{ color }}>
                  {count}
                </div>
                <div className="text-sm font-medium text-gray-900 mb-1">
                  {level} Confidence
                </div>
                <div className="text-xs text-gray-500">
                  {percentage}% of prospects
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
