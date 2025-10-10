'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  TrendingUp,
  TrendingDown,
  Activity,
  MessageSquare,
  Newspaper,
  AlertCircle,
  RefreshCw,
  Search,
  Filter,
  ChevronUp,
  ChevronDown,
  Hash,
  BarChart3,
  Zap,
  Cloud,
} from 'lucide-react';

interface HypeData {
  player_id: string;
  player_name: string;
  player_type: string;
  hype_score: number;
  hype_trend: number;
  sentiment_score: number;
  virality_score: number;
  total_mentions_24h: number;
  total_mentions_7d: number;
  engagement_rate: number;
  trending_topics: Array<{
    topic: string;
    type: string;
    mentions: number;
    sentiment: number;
  }>;
  recent_alerts: Array<{
    type: string;
    severity: string;
    title: string;
    change: number;
    created_at: string;
  }>;
}

interface LeaderboardItem {
  rank: number;
  player_id: string;
  player_name: string;
  hype_score: number;
  change_24h: number;
  change_7d: number;
  sentiment: string;
}

export default function HypePage() {
  const [selectedPlayer, setSelectedPlayer] = useState<HypeData | null>(null);
  const [leaderboard, setLeaderboard] = useState<LeaderboardItem[]>([]);
  const [filteredLeaderboard, setFilteredLeaderboard] = useState<LeaderboardItem[]>([]);
  const [trendingPlayers, setTrendingPlayers] = useState<any[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterType, setFilterType] = useState<'all' | 'prospect' | 'mlb'>('all');
  const [refreshing, setRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState<'overview' | 'social' | 'media' | 'alerts'>('overview');

  // Fetch data from API
  useEffect(() => {
    fetchLeaderboard();
  }, [filterType]);

  // Filter leaderboard based on search query
  useEffect(() => {
    if (searchQuery.trim() === '') {
      setFilteredLeaderboard(leaderboard);
    } else {
      const filtered = leaderboard.filter((player) =>
        player.player_name.toLowerCase().includes(searchQuery.toLowerCase())
      );
      setFilteredLeaderboard(filtered);
    }
  }, [searchQuery, leaderboard]);

  const fetchLeaderboard = async () => {
    try {
      setRefreshing(true);
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';
      const token = localStorage.getItem('token');

      const params = filterType !== 'all' ? `?player_type=${filterType}` : '';

      // Build headers - only add Authorization if token exists
      const headers: HeadersInit = {
        'Content-Type': 'application/json',
      };
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const response = await fetch(`${apiUrl}/api/v1/hype/leaderboard${params}`, {
        headers,
      });

      if (response.ok) {
        const data = await response.json();
        setLeaderboard(data);
        setFilteredLeaderboard(data);

        // Auto-select first player if none selected
        if (data.length > 0 && !selectedPlayer) {
          fetchPlayerDetails(data[0].player_id);
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

  const fetchPlayerDetails = async (playerId: string) => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';
      const token = localStorage.getItem('token');

      // Build headers - only add Authorization if token exists
      const headers: HeadersInit = {
        'Content-Type': 'application/json',
      };
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const response = await fetch(`${apiUrl}/api/v1/hype/player/${playerId}`, {
        headers,
      });

      if (response.ok) {
        const data = await response.json();
        setSelectedPlayer(data);
      } else {
        console.error('Failed to fetch player details:', response.status);
      }
    } catch (error) {
      console.error('Error fetching player details:', error);
    }
  };

  const getSentimentColor = (score: number) => {
    if (score > 0.5) return 'text-green-500';
    if (score < -0.5) return 'text-red-500';
    return 'text-yellow-500';
  };

  const getTrendIcon = (trend: number) => {
    if (trend > 5) return <TrendingUp className="w-5 h-5 text-green-500" />;
    if (trend < -5) return <TrendingDown className="w-5 h-5 text-red-500" />;
    return <Activity className="w-5 h-5 text-yellow-500" />;
  };

  const getHypeColor = (score: number) => {
    if (score >= 90) return 'from-purple-600 to-pink-600';
    if (score >= 75) return 'from-blue-600 to-purple-600';
    if (score >= 60) return 'from-green-600 to-blue-600';
    if (score >= 40) return 'from-yellow-600 to-green-600';
    return 'from-gray-600 to-yellow-600';
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white p-8">
      {/* Header */}
      <div className="max-w-7xl mx-auto mb-8">
        <div className="flex justify-between items-center mb-6">
          <div>
            <h1 className="text-4xl font-bold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
              HYPE Tracker
            </h1>
            <p className="text-gray-400 mt-2">
              Real-time media and social sentiment analysis for player valuation
            </p>
          </div>
          <button
            onClick={() => fetchLeaderboard()}
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
              placeholder="Search players..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-3 bg-gray-800 rounded-lg focus:ring-2 focus:ring-purple-500 outline-none"
            />
          </div>
          <div className="flex gap-2">
            {(['all', 'prospect', 'mlb'] as const).map((type) => (
              <button
                key={type}
                onClick={() => setFilterType(type)}
                className={`px-4 py-3 rounded-lg transition-all ${
                  filterType === type
                    ? 'bg-purple-600 text-white'
                    : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                }`}
              >
                {type === 'all' ? 'All' : type.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Leaderboard */}
        <div className="lg:col-span-1 space-y-4">
          <div className="bg-gray-800 rounded-xl p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-purple-400" />
                HYPE Leaderboard
              </h2>
              {searchQuery && (
                <span className="text-sm text-gray-400">
                  {filteredLeaderboard.length} results
                </span>
              )}
            </div>
            <div className="space-y-3">
              {filteredLeaderboard.length > 0 ? (
                filteredLeaderboard.map((player) => (
                <motion.div
                  key={player.player_id}
                  whileHover={{ scale: 1.02 }}
                  onClick={() => fetchPlayerDetails(player.player_id)}
                  className="p-4 bg-gray-700/50 rounded-lg cursor-pointer hover:bg-gray-700 transition-all"
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-2xl font-bold text-gray-500">
                          #{player.rank}
                        </span>
                        <span className="font-medium">{player.player_name}</span>
                      </div>
                      <div className="flex items-center gap-3 mt-2 text-sm">
                        <span className="text-gray-400">Score:</span>
                        <span className="font-bold text-purple-400">
                          {player.hype_score.toFixed(1)}
                        </span>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="flex items-center gap-1 text-sm">
                        {player.change_24h > 0 ? (
                          <ChevronUp className="w-4 h-4 text-green-500" />
                        ) : (
                          <ChevronDown className="w-4 h-4 text-red-500" />
                        )}
                        <span
                          className={
                            player.change_24h > 0 ? 'text-green-500' : 'text-red-500'
                          }
                        >
                          {Math.abs(player.change_24h).toFixed(1)}%
                        </span>
                      </div>
                      <span className="text-xs text-gray-500">24h</span>
                    </div>
                  </div>
                </motion.div>
              ))
              ) : (
                <div className="text-center py-8">
                  <Search className="w-12 h-12 mx-auto mb-3 text-gray-600" />
                  <p className="text-gray-400">
                    {searchQuery
                      ? `No players found matching "${searchQuery}"`
                      : 'No players available'
                    }
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Trending Topics */}
          <div className="bg-gray-800 rounded-xl p-6">
            <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
              <Hash className="w-5 h-5 text-pink-400" />
              Trending Topics
            </h3>
            {selectedPlayer?.trending_topics.map((topic, idx) => (
              <div key={idx} className="mb-3">
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium">{topic.topic}</span>
                  <span className="text-xs text-gray-500">
                    {topic.mentions} mentions
                  </span>
                </div>
                <div className="mt-1 h-2 bg-gray-700 rounded-full overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${(topic.mentions / 5000) * 100}%` }}
                    transition={{ duration: 1, delay: idx * 0.1 }}
                    className="h-full bg-gradient-to-r from-purple-500 to-pink-500"
                  />
                </div>
              </div>
            ))}
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
                    <span className="inline-block px-3 py-1 mt-2 bg-purple-600/20 text-purple-400 rounded-full text-sm">
                      {selectedPlayer.player_type === 'prospect' ? 'Prospect' : 'MLB'}
                    </span>
                  </div>
                  <div className="text-right">
                    <div className="text-3xl font-bold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
                      {selectedPlayer.hype_score.toFixed(1)}
                    </div>
                    <div className="flex items-center gap-1 mt-1">
                      {getTrendIcon(selectedPlayer.hype_trend)}
                      <span
                        className={
                          selectedPlayer.hype_trend > 0
                            ? 'text-green-500'
                            : selectedPlayer.hype_trend < 0
                            ? 'text-red-500'
                            : 'text-yellow-500'
                        }
                      >
                        {Math.abs(selectedPlayer.hype_trend).toFixed(1)}%
                      </span>
                    </div>
                  </div>
                </div>

                {/* HYPE Meter */}
                <div className="mb-6">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-sm text-gray-400">HYPE Level</span>
                    <Zap className="w-4 h-4 text-yellow-400" />
                  </div>
                  <div className="h-8 bg-gray-700 rounded-full overflow-hidden relative">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${selectedPlayer.hype_score}%` }}
                      transition={{ duration: 1.5, ease: 'easeOut' }}
                      className={`h-full bg-gradient-to-r ${getHypeColor(
                        selectedPlayer.hype_score
                      )} shadow-lg`}
                    />
                    <div className="absolute inset-0 flex items-center justify-center">
                      <span className="text-xs font-bold text-white drop-shadow-lg">
                        {selectedPlayer.hype_score.toFixed(0)}/100
                      </span>
                    </div>
                  </div>
                </div>

                {/* Metrics Grid */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="bg-gray-700/50 p-4 rounded-lg">
                    <div className="text-xs text-gray-400 mb-1">Sentiment</div>
                    <div className={`text-xl font-bold ${getSentimentColor(selectedPlayer.sentiment_score)}`}>
                      {selectedPlayer.sentiment_score > 0 ? '+' : ''}
                      {(selectedPlayer.sentiment_score * 100).toFixed(0)}%
                    </div>
                  </div>
                  <div className="bg-gray-700/50 p-4 rounded-lg">
                    <div className="text-xs text-gray-400 mb-1">Virality</div>
                    <div className="text-xl font-bold text-pink-400">
                      {selectedPlayer.virality_score.toFixed(1)}
                    </div>
                  </div>
                  <div className="bg-gray-700/50 p-4 rounded-lg">
                    <div className="text-xs text-gray-400 mb-1">24h Mentions</div>
                    <div className="text-xl font-bold text-blue-400">
                      {selectedPlayer.total_mentions_24h.toLocaleString()}
                    </div>
                  </div>
                  <div className="bg-gray-700/50 p-4 rounded-lg">
                    <div className="text-xs text-gray-400 mb-1">Engagement</div>
                    <div className="text-xl font-bold text-purple-400">
                      {selectedPlayer.engagement_rate.toFixed(1)}%
                    </div>
                  </div>
                </div>
              </motion.div>

              {/* Tabs */}
              <div className="bg-gray-800 rounded-xl">
                <div className="flex border-b border-gray-700">
                  {(['overview', 'social', 'media', 'alerts'] as const).map((tab) => (
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
                        <h4 className="font-medium mb-2">HYPE Analysis</h4>
                        <p className="text-sm text-gray-400">
                          {selectedPlayer.player_name} is currently {selectedPlayer.hype_score >= 70 ? 'experiencing' : 'showing'}{' '}
                          <span className={`font-medium ${selectedPlayer.hype_score >= 70 ? 'text-purple-400' : selectedPlayer.hype_score >= 40 ? 'text-yellow-400' : 'text-gray-400'}`}>
                            {selectedPlayer.hype_score >= 70 ? 'high' : selectedPlayer.hype_score >= 40 ? 'moderate' : 'low'} social engagement
                          </span>{' '}
                          with{' '}
                          <span className={getSentimentColor(selectedPlayer.sentiment_score)}>
                            {selectedPlayer.sentiment_score > 0.3 ? 'positive' : selectedPlayer.sentiment_score < -0.3 ? 'negative' : 'neutral'}
                          </span>{' '}
                          sentiment. The virality score of{' '}
                          <span className="text-pink-400 font-medium">{selectedPlayer.virality_score.toFixed(1)}</span>{' '}
                          indicates {selectedPlayer.virality_score >= 70 ? 'strong' : selectedPlayer.virality_score >= 40 ? 'moderate' : 'limited'} momentum across platforms.
                        </p>
                        <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                          <div>
                            <span className="text-gray-500">24h Mentions:</span>{' '}
                            <span className="text-white font-medium">{selectedPlayer.total_mentions_24h.toLocaleString()}</span>
                          </div>
                          <div>
                            <span className="text-gray-500">7d Mentions:</span>{' '}
                            <span className="text-white font-medium">{selectedPlayer.total_mentions_7d.toLocaleString()}</span>
                          </div>
                        </div>
                      </div>
                      <div className="bg-gray-700/30 p-4 rounded-lg">
                        <h4 className="font-medium mb-2">Investment Signal</h4>
                        <p className="text-sm text-gray-400">
                          Based on current HYPE metrics, this player shows{' '}
                          <span className={`font-medium ${selectedPlayer.hype_trend > 10 ? 'text-green-400' : selectedPlayer.hype_trend < -10 ? 'text-red-400' : 'text-yellow-400'}`}>
                            {selectedPlayer.hype_trend > 10 ? 'strong buy' : selectedPlayer.hype_trend < -10 ? 'caution' : 'hold'}
                          </span>{' '}
                          signals. The{' '}
                          {selectedPlayer.hype_trend > 0 ? 'positive' : 'negative'} trend of{' '}
                          <span className={selectedPlayer.hype_trend > 0 ? 'text-green-400' : 'text-red-400'}>
                            {selectedPlayer.hype_trend > 0 ? '+' : ''}{selectedPlayer.hype_trend.toFixed(1)}%
                          </span>{' '}
                          suggests {selectedPlayer.hype_trend > 5 ? 'increasing' : selectedPlayer.hype_trend < -5 ? 'decreasing' : 'stable'} market value.
                        </p>
                      </div>
                    </div>
                  )}

                  {activeTab === 'social' && (
                    <div className="space-y-4">
                      {selectedPlayer.total_mentions_24h > 0 ? (
                        <div className="bg-gray-700/30 p-4 rounded-lg">
                          <div className="flex items-center gap-2 mb-2">
                            <MessageSquare className="w-4 h-4 text-purple-400" />
                            <span className="font-medium">Social Activity</span>
                          </div>
                          <p className="text-sm text-gray-400 mb-3">
                            {selectedPlayer.player_name} has generated{' '}
                            <span className="text-white font-medium">{selectedPlayer.total_mentions_24h.toLocaleString()}</span>{' '}
                            mentions in the last 24 hours across social platforms.
                          </p>
                          <div className="text-xs text-gray-500">
                            Social feed integration coming soon with real-time posts from X, Bluesky, Reddit, and more.
                          </div>
                        </div>
                      ) : (
                        <div className="bg-gray-700/30 p-4 rounded-lg text-center py-8">
                          <MessageSquare className="w-12 h-12 mx-auto mb-3 text-gray-600" />
                          <p className="text-gray-400">No recent social mentions found</p>
                          <p className="text-xs text-gray-500 mt-2">
                            Social data collection is currently being developed
                          </p>
                        </div>
                      )}
                    </div>
                  )}

                  {activeTab === 'media' && (
                    <div className="space-y-4">
                      <div className="bg-gray-700/30 p-4 rounded-lg text-center py-8">
                        <Newspaper className="w-12 h-12 mx-auto mb-3 text-gray-600" />
                        <p className="text-gray-400">No recent media coverage found</p>
                        <p className="text-xs text-gray-500 mt-2">
                          Media article aggregation is currently being developed
                        </p>
                      </div>
                    </div>
                  )}

                  {activeTab === 'alerts' && (
                    <div className="space-y-4">
                      {selectedPlayer.recent_alerts && selectedPlayer.recent_alerts.length > 0 ? (
                        selectedPlayer.recent_alerts.map((alert, idx) => (
                          <div key={idx} className="bg-gray-700/30 p-4 rounded-lg">
                            <div className="flex items-start gap-3">
                              <AlertCircle className={`w-5 h-5 mt-0.5 ${
                                alert.severity === 'high' ? 'text-red-400' :
                                alert.severity === 'medium' ? 'text-yellow-400' :
                                'text-blue-400'
                              }`} />
                              <div className="flex-1">
                                <div className="flex items-center gap-2 mb-1">
                                  <h5 className="font-medium">{alert.title}</h5>
                                  <span className={`text-xs px-2 py-0.5 rounded ${
                                    alert.severity === 'high' ? 'bg-red-500/20 text-red-400' :
                                    alert.severity === 'medium' ? 'bg-yellow-500/20 text-yellow-400' :
                                    'bg-blue-500/20 text-blue-400'
                                  }`}>
                                    {alert.severity}
                                  </span>
                                </div>
                                <p className="text-sm text-gray-400 mt-1">
                                  {alert.type === 'surge' ? 'HYPE score increased' :
                                   alert.type === 'crash' ? 'HYPE score decreased' :
                                   'Notable change detected'} by{' '}
                                  <span className={`font-medium ${alert.change >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                    {alert.change >= 0 ? '+' : ''}{alert.change}%
                                  </span>
                                </p>
                                <p className="text-xs text-gray-500 mt-2">
                                  {new Date(alert.created_at).toLocaleString()}
                                </p>
                              </div>
                            </div>
                          </div>
                        ))
                      ) : (
                        <div className="bg-gray-700/30 p-4 rounded-lg text-center py-8">
                          <AlertCircle className="w-12 h-12 mx-auto mb-3 text-gray-600" />
                          <p className="text-gray-400">No active alerts</p>
                          <p className="text-xs text-gray-500 mt-2">
                            Alerts will appear here when significant HYPE changes are detected
                          </p>
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
              <p className="text-gray-400">Select a player to view HYPE details</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}