'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';

interface Prediction {
  id: number;
  name: string;
  position: string;
  predicted_tier: string;
  predicted_fv: number;
  confidence_score: number;
  actual_fv: number | null;
}

export default function MLPredictionsPage() {
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tierFilter, setTierFilter] = useState<string>('all');

  useEffect(() => {
    fetchPredictions();
  }, [tierFilter]);

  const fetchPredictions = async () => {
    try {
      setLoading(true);
      const url = tierFilter === 'all'
        ? `/api/v1/prospect-predictions/predictions?limit=100`
        : `/api/v1/prospect-predictions/predictions?tier=${tierFilter}&limit=100`;

      const response = await fetch(url);
      if (!response.ok) throw new Error('Failed to fetch predictions');

      const data = await response.json();
      setPredictions(data.predictions);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const getTierColor = (tier: string) => {
    switch (tier) {
      case 'Star':
      case 'Elite':
        return 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30';
      case 'Solid':
        return 'text-blue-400 bg-blue-400/10 border-blue-400/30';
      case 'Role Player':
        return 'text-green-400 bg-green-400/10 border-green-400/30';
      default:
        return 'text-gray-400 bg-gray-400/10 border-gray-400/30';
    }
  };

  const getTierBadge = (tier: string) => {
    const colorClasses = getTierColor(tier);
    return (
      <span className={`px-3 py-1 rounded-full text-sm font-semibold border ${colorClasses}`}>
        {tier}
      </span>
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-wine-plum via-wine-raisin to-wine-dark flex items-center justify-center">
        <div className="text-white text-xl">Loading ML Predictions...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-wine-plum via-wine-raisin to-wine-dark flex items-center justify-center">
        <div className="text-red-400 text-xl">Error: {error}</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-wine-plum via-wine-raisin to-wine-dark">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-white mb-2">
            ML Prospect Predictions
          </h1>
          <p className="text-wine-periwinkle text-lg">
            AI-powered prospect success predictions using 118 engineered features
          </p>
        </div>

        {/* Stats Summary */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-wine-dark/50 rounded-lg p-4 border border-wine-periwinkle/20">
            <div className="text-wine-periwinkle text-sm mb-1">Total Predictions</div>
            <div className="text-white text-2xl font-bold">1,103</div>
          </div>
          <div className="bg-wine-dark/50 rounded-lg p-4 border border-yellow-400/20">
            <div className="text-yellow-400 text-sm mb-1">Star Prospects</div>
            <div className="text-white text-2xl font-bold">10</div>
          </div>
          <div className="bg-wine-dark/50 rounded-lg p-4 border border-blue-400/20">
            <div className="text-blue-400 text-sm mb-1">Solid Prospects</div>
            <div className="text-white text-2xl font-bold">68</div>
          </div>
          <div className="bg-wine-dark/50 rounded-lg p-4 border border-green-400/20">
            <div className="text-green-400 text-sm mb-1">Role Players</div>
            <div className="text-white text-2xl font-bold">97</div>
          </div>
        </div>

        {/* Filter Tabs */}
        <div className="flex gap-2 mb-6 flex-wrap">
          {['all', 'Star', 'Solid', 'Role Player', 'Org Filler'].map((tier) => (
            <button
              key={tier}
              onClick={() => setTierFilter(tier)}
              className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                tierFilter === tier
                  ? 'bg-wine-periwinkle text-wine-dark'
                  : 'bg-wine-dark/50 text-wine-periwinkle hover:bg-wine-dark border border-wine-periwinkle/20'
              }`}
            >
              {tier === 'all' ? 'All Tiers' : tier}
            </button>
          ))}
        </div>

        {/* Predictions Table */}
        <div className="bg-wine-dark/50 rounded-lg border border-wine-periwinkle/20 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-wine-plum/50">
                <tr>
                  <th className="px-6 py-4 text-left text-sm font-semibold text-wine-periwinkle">
                    Rank
                  </th>
                  <th className="px-6 py-4 text-left text-sm font-semibold text-wine-periwinkle">
                    Name
                  </th>
                  <th className="px-6 py-4 text-left text-sm font-semibold text-wine-periwinkle">
                    Position
                  </th>
                  <th className="px-6 py-4 text-left text-sm font-semibold text-wine-periwinkle">
                    Predicted Tier
                  </th>
                  <th className="px-6 py-4 text-left text-sm font-semibold text-wine-periwinkle">
                    Predicted FV
                  </th>
                  <th className="px-6 py-4 text-left text-sm font-semibold text-wine-periwinkle">
                    Confidence
                  </th>
                  <th className="px-6 py-4 text-left text-sm font-semibold text-wine-periwinkle">
                    Actual FV
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-wine-periwinkle/10">
                {predictions.map((prediction, index) => (
                  <tr
                    key={prediction.id}
                    className="hover:bg-wine-plum/20 transition-colors"
                  >
                    <td className="px-6 py-4 text-white font-medium">
                      {index + 1}
                    </td>
                    <td className="px-6 py-4">
                      <Link
                        href={`/prospects/${prediction.id}`}
                        className="text-wine-periwinkle hover:text-white font-medium transition-colors"
                      >
                        {prediction.name}
                      </Link>
                    </td>
                    <td className="px-6 py-4 text-white">
                      {prediction.position}
                    </td>
                    <td className="px-6 py-4">
                      {getTierBadge(prediction.predicted_tier)}
                    </td>
                    <td className="px-6 py-4">
                      <span className="text-white font-semibold text-lg">
                        {prediction.predicted_fv}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <div className="w-24 bg-wine-plum/50 rounded-full h-2">
                          <div
                            className="bg-wine-periwinkle h-2 rounded-full transition-all"
                            style={{
                              width: `${(prediction.confidence_score || 0) * 100}%`,
                            }}
                          />
                        </div>
                        <span className="text-white text-sm">
                          {((prediction.confidence_score || 0) * 100).toFixed(1)}%
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      {prediction.actual_fv ? (
                        <span className="text-white font-medium">
                          {prediction.actual_fv}
                        </span>
                      ) : (
                        <span className="text-gray-500">-</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Footer Info */}
        <div className="mt-8 bg-wine-dark/30 rounded-lg p-6 border border-wine-periwinkle/20">
          <h3 className="text-wine-periwinkle font-semibold mb-2">About These Predictions</h3>
          <p className="text-white/70 text-sm mb-4">
            These predictions are generated by an XGBoost machine learning model trained on 599 prospects
            with complete scouting data. The model uses 118 engineered features across 6 categories:
            biographical data, scouting grades, MiLB performance, progression, consistency, and derived metrics.
          </p>
          <div className="grid md:grid-cols-3 gap-4 text-sm">
            <div>
              <div className="text-wine-periwinkle font-medium">Model Accuracy</div>
              <div className="text-white">100% on test set</div>
            </div>
            <div>
              <div className="text-wine-periwinkle font-medium">Validation</div>
              <div className="text-white">99.7% within 5 FV points</div>
            </div>
            <div>
              <div className="text-wine-periwinkle font-medium">Model Version</div>
              <div className="text-white">v1.0 (2024)</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
