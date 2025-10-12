'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  TrendingUp,
  TrendingDown,
  Activity,
  Zap,
  Target,
  Award,
  BarChart3,
  Brain,
  RefreshCw,
  Search,
  Filter,
  ChevronUp,
  ChevronDown,
  ArrowUpDown,
  Sparkles,
  AlertCircle,
  Info,
  TrendingFlat,
} from 'lucide-react';

interface MLProjection {
  player_id: string;
  player_name: string;
  position: string;
  age: number | null;
  organization: string | null;
  level: string | null;
  success_probability: number | null;
  breakout_score: number | null;
  dynasty_rank: number | null;
  investment_signal: 'strong_buy' | 'buy' | 'hold' | 'caution' | 'sell';
  signal_strength: number;
  signal_reasoning: string;
  eta_year: number | null;
  eta_confidence: number | null;
  projected_stats: Record<string, number>;
  overall_confidence: 'high' | 'medium' | 'low';
  data_quality_score: number;
  last_updated: string;
}

interface LeaderboardItem {
  rank: number;
  player_id: string;
  player_name: string;
  position: string;
  organization: string | null;
  success_probability: number | null;
  breakout_score: number | null;
  dynasty_rank: number | null;
  investment_signal: string | null;
  confidence_level: string | null;
  change_7d: number | null;
}

interface BreakoutCandidate {
  rank: number;
  player_id: string;
  player_name: string;
  position: string;
  organization: string | null;
  breakout_score: number;
  max_improvement_rate: number;
  improved_metrics: string[];
  signal: string;
  calculated_at: string;
}

interface FeatureImportance {
  feature_name: string;
  importance: number;
  feature_value: any;
  impact: string;
}

export default function PredictionsPage() {
  const [selectedPlayer, setSelectedPlayer] = useState<MLProjection | null>(null);
  const [leaderboard, setLeaderboard] = useState<LeaderboardItem[]>([]);
  const [filteredLeaderboard, setFilteredLeaderboard] = useState<LeaderboardItem[]>([]);
  const [breakoutCandidates, setBreakoutCandidates] = useState<BreakoutCandidate[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterPosition, setFilterPosition] = useState<string>('all');
  const [sortBy, setSortBy] = useState<'success_probability' | 'breakout_score' | 'dynasty_rank'>('success_probability');
  const [refreshing, setRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState<'overview' | 'breakout' | 'features' | 'projections'>('overview');
  const [featureImportances, setFeatureImportances] = useState<FeatureImportance[]>([]);

  // Fetch leaderboard
  useEffect(() => {
    fetchLeaderboard();
    fetchBreakoutCandidates();
  }, [sortBy, filterPosition]);

  // Filter leaderboard based on search
  useEffect(() => {
    let filtered = [...leaderboard];

    if (searchQuery.trim() !== '') {
      filtered = filtered.filter((player) =>
        player.player_name.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }

    filtered = filtered.map((player, index) => ({
      ...player,
      rank: index + 1
    }));

    setFilteredLeaderboard(filtered);
  }, [searchQuery, leaderboard]);

  const fetchLeaderboard = async () => {
    try {
      setRefreshing(true);
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';
      const token = localStorage.getItem('token');

      const queryParams = new URLSearchParams();
      queryParams.append('sort_by', sortBy);
      queryParams.append('limit', '100');
      if (filterPosition !== 'all') {
        queryParams.append('position', filterPosition);
      }

      const headers: HeadersInit = {
        'Content-Type': 'application/json',
      };
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const response = await fetch(`${apiUrl}/api/v1/ml/leaderboard?${queryParams.toString()}`, {
        headers,
      });

      if (response.ok) {
        const data = await response.json();
        setLeaderboard(data.leaderboard);
        setFilteredLeaderboard(data.leaderboard);

        // Auto-select first player if none selected
        if (data.leaderboard.length > 0 && !selectedPlayer) {
          fetchPlayerProjection(data.leaderboard[0].player_id);
        }
      } else {
        console.error('Failed to fetch leaderboard:', response.status);
      }
    } catch (error) {
      console.error('Error fetching leaderboard:', error);
    } finally {
      setRefreshing(false);
    }
  };

  const fetchPlayerProjection = async (playerId: string) => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';
      const token = localStorage.getItem('token');

      const headers: HeadersInit = {
        'Content-Type': 'application/json',
      };
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const response = await fetch(`${apiUrl}/api/v1/ml/player/${playerId}`, {
        headers,
      });

      if (response.ok) {
        const data = await response.json();
        setSelectedPlayer(data);

        // Fetch SHAP feature importances (optional - may not exist for all players)
        try {
          const featResponse = await fetch(`${apiUrl}/api/v1/ml/player/${playerId}/success-probability?include_features=true`, {
            headers,
          });

          if (featResponse.ok) {
            const featData = await featResponse.json();
            setFeatureImportances(featData.feature_importances || []);
          } else if (featResponse.status === 404) {
            // No ML prediction available for this player - this is ok
            setFeatureImportances([]);
          }
        } catch (featError) {
          // Feature importances are optional - don't fail if they're missing
          console.log('Feature importances not available for this player');
          setFeatureImportances([]);
        }
      } else {
        console.error('Failed to fetch player projection:', response.status);
      }
    } catch (error) {
      console.error('Error fetching player projection:', error);
    }
  };

  const fetchBreakoutCandidates = async () => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';
      const response = await fetch(`${apiUrl}/api/v1/ml/breakout-candidates?limit=10&min_score=60`);

      if (response.ok) {
        const data = await response.json();
        setBreakoutCandidates(data);
      }
    } catch (error) {
      console.error('Error fetching breakout candidates:', error);
    }
  };

  const getSignalColor = (signal: string | undefined | null) => {
    if (!signal) return 'from-gray-500 to-gray-600';

    switch (signal) {
      case 'strong_buy':
        return 'from-green-600 to-emerald-600';
      case 'buy':
        return 'from-green-500 to-green-600';
      case 'hold':
        return 'from-yellow-500 to-yellow-600';
      case 'caution':
        return 'from-orange-500 to-orange-600';
      case 'sell':
        return 'from-red-500 to-red-600';
      default:
        return 'from-gray-500 to-gray-600';
    }
  };

  const getSignalIcon = (signal: string | undefined | null) => {
    if (!signal) return <Activity className="w-5 h-5" />;

    switch (signal) {
      case 'strong_buy':
        return <ChevronUp className="w-5 h-5" />;
      case 'buy':
        return <TrendingUp className="w-5 h-5" />;
      case 'hold':
        return <TrendingFlat className="w-5 h-5" />;
      case 'caution':
        return <AlertCircle className="w-5 h-5" />;
      case 'sell':
        return <TrendingDown className="w-5 h-5" />;
      default:
        return <Activity className="w-5 h-5" />;
    }
  };

  const getSignalText = (signal: string | undefined | null) => {
    if (!signal) return 'N/A';

    switch (signal) {
      case 'strong_buy':
        return 'STRONG BUY';
      case 'buy':
        return 'BUY';
      case 'hold':
        return 'HOLD';
      case 'caution':
        return 'CAUTION';
      case 'sell':
        return 'SELL';
      default:
        return signal.toUpperCase();
    }
  };

  const getConfidenceColor = (confidence: string | undefined | null) => {
    if (!confidence) return 'text-gray-400';

    switch (confidence.toLowerCase()) {
      case 'high':
        return 'text-green-400';
      case 'medium':
        return 'text-yellow-400';
      case 'low':
        return 'text-red-400';
      default:
        return 'text-gray-400';
    }
  };

  const getBreakoutSignalColor = (signal: string) => {
    switch (signal) {
      case 'hot_streak':
        return 'from-red-500 to-orange-500';
      case 'moderate_improvement':
        return 'from-yellow-500 to-orange-500';
      default:
        return 'from-gray-500 to-gray-600';
    }
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white p-8">
      {/* Header */}
      <div className="max-w-7xl mx-auto mb-8">
        <div className="flex justify-between items-center mb-6">
          <div>
            <h1 className="text-4xl font-bold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent flex items-center gap-3">
              <Brain className="w-10 h-10 text-purple-400" />
              ML Predictions
            </h1>
            <p className="text-gray-400 mt-2">
              AI-powered prospect analysis with actionable fantasy insights
            </p>
          </div>
          <button
            onClick={() => {
              fetchLeaderboard();
              fetchBreakoutCandidates();
            }}
            className={`p-3 bg-gray-800 rounded-lg hover:bg-gray-700 transition-all ${
              refreshing ? 'animate-spin' : ''
            }`}
            disabled={refreshing}
          >
            <RefreshCw className="w-5 h-5" />
          </button>
        </div>

        {/* Search and Filter Bar */}
        <div className="flex gap-4 mb-6">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              placeholder="Search prospects..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-3 bg-gray-800 rounded-lg focus:ring-2 focus:ring-purple-500 outline-none"
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setFilterPosition('all')}
              className={`px-4 py-3 rounded-lg transition-all ${
                filterPosition === 'all'
                  ? 'bg-purple-600 text-white'
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
              }`}
            >
              All
            </button>
            {['SS', '2B', 'OF', 'SP', 'C'].map((pos) => (
              <button
                key={pos}
                onClick={() => setFilterPosition(pos)}
                className={`px-4 py-3 rounded-lg transition-all ${
                  filterPosition === pos
                    ? 'bg-purple-600 text-white'
                    : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                }`}
              >
                {pos}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Leaderboard & Breakout Candidates */}
        <div className="lg:col-span-1 space-y-4">
          {/* Leaderboard */}
          <div className="bg-gray-800 rounded-xl p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-purple-400" />
                Predictions
              </h2>
              <div className="flex items-center gap-3">
                {searchQuery && (
                  <span className="text-sm text-gray-400">
                    {filteredLeaderboard.length} results
                  </span>
                )}
                <button
                  onClick={() => {
                    const order: Array<'success_probability' | 'breakout_score' | 'dynasty_rank'> = [
                      'success_probability',
                      'breakout_score',
                      'dynasty_rank',
                    ];
                    const currentIndex = order.indexOf(sortBy);
                    const nextIndex = (currentIndex + 1) % order.length;
                    setSortBy(order[nextIndex]);
                  }}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all text-sm font-medium bg-purple-600 text-white hover:bg-purple-700`}
                  title={`Sort by ${sortBy.replace('_', ' ')}`}
                >
                  <ArrowUpDown className="w-4 h-4" />
                  <span>
                    {sortBy === 'success_probability' && 'Success'}
                    {sortBy === 'breakout_score' && 'Breakout'}
                    {sortBy === 'dynasty_rank' && 'Dynasty'}
                  </span>
                </button>
              </div>
            </div>
            <div className="space-y-3 max-h-[500px] overflow-y-auto">
              {filteredLeaderboard.length > 0 ? (
                filteredLeaderboard.map((player) => (
                  <motion.div
                    key={player.player_id}
                    whileHover={{ scale: 1.02 }}
                    onClick={() => fetchPlayerProjection(player.player_id)}
                    className={`p-4 rounded-lg cursor-pointer transition-all ${
                      selectedPlayer?.player_id === player.player_id
                        ? 'bg-purple-600/20 border-2 border-purple-500'
                        : 'bg-gray-700/50 hover:bg-gray-700'
                    }`}
                  >
                    <div className="flex justify-between items-start">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-lg font-bold text-gray-500">
                            #{player.rank}
                          </span>
                          <span className="font-medium">{player.player_name}</span>
                          <span className="text-xs px-2 py-0.5 bg-gray-600 rounded">
                            {player.position}
                          </span>
                        </div>
                        <div className="text-xs text-gray-400 mb-2">
                          {player.organization}
                        </div>
                        <div className="flex items-center gap-2">
                          {player.success_probability !== null && (
                            <div className="text-sm">
                              <span className="text-gray-400">Success: </span>
                              <span className="font-bold text-purple-400">
                                {(player.success_probability * 100).toFixed(0)}%
                              </span>
                            </div>
                          )}
                          {player.breakout_score !== null && (
                            <div className="text-sm">
                              <span className="text-gray-400">Breakout: </span>
                              <span className="font-bold text-orange-400">
                                {player.breakout_score.toFixed(0)}
                              </span>
                            </div>
                          )}
                        </div>
                      </div>
                      <div className="text-right">
                        <div
                          className={`inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-bold bg-gradient-to-r ${getSignalColor(
                            player.investment_signal
                          )}`}
                        >
                          {getSignalIcon(player.investment_signal)}
                          {getSignalText(player.investment_signal)}
                        </div>
                        <div
                          className={`text-xs mt-1 ${getConfidenceColor(
                            player.confidence_level
                          )}`}
                        >
                          {player.confidence_level || 'N/A'} conf.
                        </div>
                      </div>
                    </div>
                  </motion.div>
                ))
              ) : (
                <div className="text-center py-8">
                  <Search className="w-12 h-12 mx-auto mb-3 text-gray-600" />
                  <p className="text-gray-400">
                    {searchQuery
                      ? `No prospects found matching "${searchQuery}"`
                      : 'No prospects available'}
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Breakout Candidates */}
          <div className="bg-gray-800 rounded-xl p-6">
            <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-orange-400" />
              Breakout Candidates
            </h3>
            <div className="space-y-3">
              {breakoutCandidates.slice(0, 5).map((candidate) => (
                <div
                  key={candidate.player_id}
                  onClick={() => fetchPlayerProjection(candidate.player_id)}
                  className="p-3 bg-gray-700/50 rounded-lg cursor-pointer hover:bg-gray-700 transition-all"
                >
                  <div className="flex justify-between items-start mb-2">
                    <div>
                      <div className="font-medium text-sm">{candidate.player_name}</div>
                      <div className="text-xs text-gray-400">{candidate.position}</div>
                    </div>
                    <div
                      className={`px-2 py-1 rounded text-xs font-bold bg-gradient-to-r ${getBreakoutSignalColor(
                        candidate.signal
                      )}`}
                    >
                      {candidate.breakout_score.toFixed(0)}
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {candidate.improved_metrics.slice(0, 2).map((metric, idx) => (
                      <span
                        key={idx}
                        className="text-xs px-2 py-0.5 bg-green-500/20 text-green-400 rounded"
                      >
                        {metric}
                      </span>
                    ))}
                    {candidate.improved_metrics.length > 2 && (
                      <span className="text-xs px-2 py-0.5 bg-gray-600 rounded">
                        +{candidate.improved_metrics.length - 2}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column - Player Details */}
        <div className="lg:col-span-2">
          {selectedPlayer ? (
            <div className="space-y-6">
              {/* Player Header Card */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-gray-800 rounded-xl p-6"
              >
                <div className="flex justify-between items-start mb-6">
                  <div>
                    <h2 className="text-2xl font-bold">{selectedPlayer.player_name}</h2>
                    <div className="flex items-center gap-2 mt-2">
                      <span className="px-3 py-1 bg-purple-600/20 text-purple-400 rounded-full text-sm">
                        {selectedPlayer.position}
                      </span>
                      <span className="text-sm text-gray-400">
                        {selectedPlayer.organization} • {selectedPlayer.level}
                      </span>
                      {selectedPlayer.age && (
                        <span className="text-sm text-gray-400">• Age {selectedPlayer.age}</span>
                      )}
                    </div>
                  </div>
                  <div className="text-right">
                    <div
                      className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-lg font-bold bg-gradient-to-r ${getSignalColor(
                        selectedPlayer.investment_signal
                      )}`}
                    >
                      {getSignalIcon(selectedPlayer.investment_signal)}
                      {getSignalText(selectedPlayer.investment_signal)}
                    </div>
                    <div className="text-sm text-gray-400 mt-2">
                      Signal Strength: {selectedPlayer.signal_strength.toFixed(0)}/100
                    </div>
                  </div>
                </div>

                {/* Core Metrics Grid */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                  {selectedPlayer.success_probability !== null && (
                    <div className="bg-gray-700/50 p-4 rounded-lg">
                      <div className="flex items-center gap-2 mb-1">
                        <Target className="w-4 h-4 text-purple-400" />
                        <div className="text-xs text-gray-400">MLB Success</div>
                      </div>
                      <div className="text-2xl font-bold text-purple-400">
                        {(selectedPlayer.success_probability * 100).toFixed(0)}%
                      </div>
                    </div>
                  )}
                  {selectedPlayer.breakout_score !== null && (
                    <div className="bg-gray-700/50 p-4 rounded-lg">
                      <div className="flex items-center gap-2 mb-1">
                        <Zap className="w-4 h-4 text-orange-400" />
                        <div className="text-xs text-gray-400">Breakout</div>
                      </div>
                      <div className="text-2xl font-bold text-orange-400">
                        {selectedPlayer.breakout_score.toFixed(0)}
                      </div>
                    </div>
                  )}
                  {selectedPlayer.dynasty_rank !== null && (
                    <div className="bg-gray-700/50 p-4 rounded-lg">
                      <div className="flex items-center gap-2 mb-1">
                        <Award className="w-4 h-4 text-yellow-400" />
                        <div className="text-xs text-gray-400">Dynasty Rank</div>
                      </div>
                      <div className="text-2xl font-bold text-yellow-400">
                        #{selectedPlayer.dynasty_rank}
                      </div>
                    </div>
                  )}
                  <div className="bg-gray-700/50 p-4 rounded-lg">
                    <div className="flex items-center gap-2 mb-1">
                      <Info className="w-4 h-4 text-blue-400" />
                      <div className="text-xs text-gray-400">Confidence</div>
                    </div>
                    <div
                      className={`text-2xl font-bold ${getConfidenceColor(
                        selectedPlayer.overall_confidence
                      )}`}
                    >
                      {selectedPlayer.overall_confidence.toUpperCase()}
                    </div>
                  </div>
                </div>

                {/* Signal Reasoning */}
                <div className="bg-gray-700/30 p-4 rounded-lg">
                  <h4 className="font-medium mb-2 flex items-center gap-2">
                    <Brain className="w-4 h-4 text-purple-400" />
                    Investment Analysis
                  </h4>
                  <p className="text-sm text-gray-300 leading-relaxed">
                    {selectedPlayer.signal_reasoning}
                  </p>
                </div>
              </motion.div>

              {/* Tabs */}
              <div className="bg-gray-800 rounded-xl">
                <div className="flex border-b border-gray-700">
                  {(['overview', 'breakout', 'features', 'projections'] as const).map((tab) => (
                    <button
                      key={tab}
                      onClick={() => setActiveTab(tab)}
                      className={`flex-1 py-3 px-4 text-sm font-medium transition-all ${
                        activeTab === tab
                          ? 'text-purple-400 border-b-2 border-purple-400'
                          : 'text-gray-400 hover:text-white'
                      }`}
                    >
                      {tab.charAt(0).toUpperCase() + tab.slice(1)}
                    </button>
                  ))}
                </div>

                <div className="p-6">
                  {activeTab === 'overview' && (
                    <div className="space-y-4">
                      <div className="bg-gray-700/30 p-4 rounded-lg">
                        <h4 className="font-medium mb-2">Data Quality</h4>
                        <div className="flex items-center gap-3">
                          <div className="flex-1 h-4 bg-gray-700 rounded-full overflow-hidden">
                            <motion.div
                              initial={{ width: 0 }}
                              animate={{
                                width: `${selectedPlayer.data_quality_score * 100}%`,
                              }}
                              transition={{ duration: 1 }}
                              className={`h-full ${
                                selectedPlayer.data_quality_score >= 0.7
                                  ? 'bg-green-500'
                                  : selectedPlayer.data_quality_score >= 0.5
                                  ? 'bg-yellow-500'
                                  : 'bg-red-500'
                              }`}
                            />
                          </div>
                          <span className="text-sm font-bold">
                            {(selectedPlayer.data_quality_score * 100).toFixed(0)}%
                          </span>
                        </div>
                        <p className="text-xs text-gray-400 mt-2">
                          Based on available ML predictions, stats, and scouting data
                        </p>
                      </div>

                      {selectedPlayer.eta_year && (
                        <div className="bg-gray-700/30 p-4 rounded-lg">
                          <h4 className="font-medium mb-2">ETA Projection</h4>
                          <div className="flex items-center gap-3">
                            <div className="text-3xl font-bold text-blue-400">
                              {selectedPlayer.eta_year}
                            </div>
                            {selectedPlayer.eta_confidence && (
                              <div className="text-sm text-gray-400">
                                {(selectedPlayer.eta_confidence * 100).toFixed(0)}% confidence
                              </div>
                            )}
                          </div>
                        </div>
                      )}

                      <div className="bg-gray-700/30 p-4 rounded-lg">
                        <h4 className="font-medium mb-2">Last Updated</h4>
                        <p className="text-sm text-gray-400">
                          {new Date(selectedPlayer.last_updated).toLocaleString()}
                        </p>
                      </div>
                    </div>
                  )}

                  {activeTab === 'breakout' && (
                    <div className="bg-gray-700/30 p-4 rounded-lg">
                      <p className="text-sm text-gray-400 text-center py-8">
                        Breakout analysis available for players with sufficient historical data
                      </p>
                    </div>
                  )}

                  {activeTab === 'features' && (
                    <div className="space-y-3">
                      <h4 className="font-medium mb-3 flex items-center gap-2">
                        <Brain className="w-4 h-4 text-purple-400" />
                        Feature Importances (SHAP Values)
                      </h4>
                      {featureImportances.length > 0 ? (
                        featureImportances.map((feature, idx) => (
                          <div key={idx} className="bg-gray-700/30 p-3 rounded-lg">
                            <div className="flex justify-between items-start mb-2">
                              <div>
                                <div className="font-medium text-sm">
                                  {feature.feature_name
                                    .replace(/_/g, ' ')
                                    .replace(/\b\w/g, (l) => l.toUpperCase())}
                                </div>
                                <div className="text-xs text-gray-400">
                                  Value: {JSON.stringify(feature.feature_value)}
                                </div>
                              </div>
                              <span
                                className={`text-xs px-2 py-1 rounded ${
                                  feature.impact === 'positive'
                                    ? 'bg-green-500/20 text-green-400'
                                    : feature.impact === 'negative'
                                    ? 'bg-red-500/20 text-red-400'
                                    : 'bg-gray-600 text-gray-400'
                                }`}
                              >
                                {feature.impact}
                              </span>
                            </div>
                            <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                              <div
                                className="h-full bg-gradient-to-r from-purple-500 to-pink-500"
                                style={{
                                  width: `${Math.min(feature.importance * 100, 100)}%`,
                                }}
                              />
                            </div>
                          </div>
                        ))
                      ) : (
                        <div className="text-center py-8 text-gray-400 text-sm">
                          No feature importance data available
                        </div>
                      )}
                    </div>
                  )}

                  {activeTab === 'projections' && (
                    <div className="space-y-3">
                      <h4 className="font-medium mb-3">Projected Stats</h4>
                      {selectedPlayer.projected_stats && Object.keys(selectedPlayer.projected_stats).length > 0 ? (
                        <div className="grid grid-cols-2 gap-3">
                          {Object.entries(selectedPlayer.projected_stats).map(
                            ([stat, value]) => (
                              <div key={stat} className="bg-gray-700/30 p-3 rounded-lg">
                                <div className="text-xs text-gray-400 mb-1">
                                  {stat.replace(/_/g, ' ').toUpperCase()}
                                </div>
                                <div className="text-xl font-bold text-blue-400">
                                  {typeof value === 'number' ? value.toFixed(3) : value}
                                </div>
                              </div>
                            )
                          )}
                        </div>
                      ) : (
                        <div className="text-center py-8 text-gray-400 text-sm">
                          No projected stats available
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-gray-800 rounded-xl p-12 text-center">
              <Activity className="w-16 h-16 mx-auto mb-4 text-gray-600" />
              <p className="text-gray-400">Select a prospect to view ML predictions</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
