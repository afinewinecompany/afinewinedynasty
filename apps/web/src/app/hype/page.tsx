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
  ExternalLink,
  Heart,
  Share2,
  ArrowUpDown,
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
  search_trends?: {
    search_interest: number;
    search_interest_avg_7d: number;
    search_interest_avg_30d: number;
    growth_rate: number;
    regional_interest: Record<string, number>;
    related_queries: Array<{ query: string; value: number }>;
    rising_queries: Array<{ query: string; value: string }>;
    collected_at: string;
    data_period_start: string;
    data_period_end: string;
  };
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

interface SocialMention {
  id: number;
  platform: string;
  author_handle: string;
  content: string;
  url: string;
  likes: number;
  shares: number;
  sentiment: string;
  posted_at: string;
}

interface MediaArticle {
  id: number;
  source: string;
  title: string;
  url: string;
  summary: string;
  sentiment: string;
  published_at: string;
}

export default function HypePage() {
  const [selectedPlayer, setSelectedPlayer] = useState<HypeData | null>(null);
  const [leaderboard, setLeaderboard] = useState<LeaderboardItem[]>([]);
  const [filteredLeaderboard, setFilteredLeaderboard] = useState<LeaderboardItem[]>([]);
  const [trendingPlayers, setTrendingPlayers] = useState<any[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterType, setFilterType] = useState<'all' | 'prospect' | 'mlb'>('all');
  const [refreshing, setRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState<'overview' | 'social' | 'media' | 'trends' | 'alerts'>('overview');
  const [socialMentions, setSocialMentions] = useState<SocialMention[]>([]);
  const [loadingSocial, setLoadingSocial] = useState(false);
  const [mediaArticles, setMediaArticles] = useState<MediaArticle[]>([]);
  const [loadingMedia, setLoadingMedia] = useState(false);
  const [sortBy, setSortBy] = useState<'hype_score' | 'change_24h'>('change_24h');
  const [changePeriod, setChangePeriod] = useState<'24h' | '7d' | '14d' | '21d'>('7d'); // Default to 7 days

  // Fetch data from API
  useEffect(() => {
    fetchLeaderboard();
  }, [filterType, changePeriod]); // Re-fetch when period changes

  // Filter and sort leaderboard based on search query and sort preference
  useEffect(() => {
    let filtered = [...leaderboard];

    // Apply search filter
    if (searchQuery.trim() !== '') {
      filtered = filtered.filter((player) =>
        player.player_name.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }

    // Apply sorting
    if (sortBy === 'change_24h') {
      // Sort by percentage change (highest to lowest)
      filtered.sort((a, b) => b.change_24h - a.change_24h);
    } else {
      // Sort by hype score (highest to lowest - default)
      filtered.sort((a, b) => b.hype_score - a.hype_score);
    }

    // Re-assign ranks based on current sort
    filtered = filtered.map((player, index) => ({
      ...player,
      rank: index + 1
    }));

    setFilteredLeaderboard(filtered);
  }, [searchQuery, leaderboard, sortBy]);

  const fetchLeaderboard = async () => {
    try {
      setRefreshing(true);
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';
      const token = localStorage.getItem('token');

      // Build params with limit=100 to get all players (API max)
      const queryParams = new URLSearchParams();
      queryParams.append('limit', '100'); // Get all players for searchability
      queryParams.append('change_period', changePeriod); // Pass selected time period
      if (filterType !== 'all') {
        queryParams.append('player_type', filterType);
      }
      const params = `?${queryParams.toString()}`;

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
        // Fetch social mentions and media articles when player is selected
        fetchSocialMentions(playerId);
        fetchMediaArticles(playerId);
      } else {
        console.error('Failed to fetch player details:', response.status);
      }
    } catch (error) {
      console.error('Error fetching player details:', error);
    }
  };

  const fetchSocialMentions = async (playerId: string) => {
    try {
      setLoadingSocial(true);
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';
      const token = localStorage.getItem('token');

      const headers: HeadersInit = {
        'Content-Type': 'application/json',
      };
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const response = await fetch(`${apiUrl}/api/v1/hype/player/${playerId}/social-feed?limit=10`, {
        headers,
      });

      if (response.ok) {
        const data = await response.json();
        setSocialMentions(data);
      } else {
        console.error('Failed to fetch social mentions:', response.status);
        setSocialMentions([]);
      }
    } catch (error) {
      console.error('Error fetching social mentions:', error);
      setSocialMentions([]);
    } finally {
      setLoadingSocial(false);
    }
  };

  const fetchMediaArticles = async (playerId: string) => {
    try {
      setLoadingMedia(true);
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

      const response = await fetch(`${apiUrl}/api/v1/hype/player/${playerId}/media-feed?limit=10`);

      if (response.ok) {
        const data = await response.json();
        setMediaArticles(data);
      } else {
        console.error('Failed to fetch media articles:', response.status);
        setMediaArticles([]);
      }
    } catch (error) {
      console.error('Error fetching media articles:', error);
      setMediaArticles([]);
    } finally {
      setLoadingMedia(false);
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

  const getPlatformIcon = (platform: string) => {
    switch (platform.toLowerCase()) {
      case 'twitter':
      case 'x':
        return <div className="w-4 h-4 text-blue-400">𝕏</div>;
      case 'bluesky':
        return <Cloud className="w-4 h-4 text-sky-400" />;
      case 'reddit':
        return <div className="w-4 h-4 text-orange-500">▲</div>;
      case 'instagram':
        return <div className="w-4 h-4 text-pink-400">📷</div>;
      case 'tiktok':
        return <div className="w-4 h-4 text-black">🎵</div>;
      case 'facebook':
        return <div className="w-4 h-4 text-blue-600">f</div>;
      default:
        return <MessageSquare className="w-4 h-4 text-gray-400" />;
    }
  };

  const getPlatformColor = (platform: string) => {
    switch (platform.toLowerCase()) {
      case 'twitter':
      case 'x':
        return 'text-blue-400';
      case 'bluesky':
        return 'text-sky-400';
      case 'reddit':
        return 'text-orange-500';
      case 'instagram':
        return 'text-pink-400';
      case 'tiktok':
        return 'text-black';
      case 'facebook':
        return 'text-blue-600';
      default:
        return 'text-gray-400';
    }
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
          {/* Time Period Selector */}
          <div className="bg-gray-800 rounded-xl p-4">
            <h3 className="text-sm font-medium text-gray-400 mb-3">% Change Period</h3>
            <div className="grid grid-cols-4 gap-2">
              {(['24h', '7d', '14d', '21d'] as const).map((period) => (
                <button
                  key={period}
                  onClick={() => setChangePeriod(period)}
                  className={`px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                    changePeriod === period
                      ? 'bg-purple-600 text-white shadow-lg shadow-purple-500/50'
                      : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                  }`}
                >
                  {period === '24h' ? '24 Hours' : period === '7d' ? '7 Days' : period === '14d' ? '14 Days' : '21 Days'}
                </button>
              ))}
            </div>
          </div>

          <div className="bg-gray-800 rounded-xl p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-purple-400" />
                HYPE Leaderboard
              </h2>
              <div className="flex items-center gap-3">
                {searchQuery && (
                  <span className="text-sm text-gray-400">
                    {filteredLeaderboard.length} results
                  </span>
                )}
                <button
                  onClick={() => setSortBy(sortBy === 'hype_score' ? 'change_24h' : 'hype_score')}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all text-sm font-medium ${
                    sortBy === 'change_24h'
                      ? 'bg-purple-600 text-white hover:bg-purple-700'
                      : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                  }`}
                  title={`Currently sorted by ${sortBy === 'change_24h' ? '24h % Change' : 'HYPE Score'}. Click to toggle.`}
                >
                  <ArrowUpDown className="w-4 h-4" />
                  <span>
                    Sort: {sortBy === 'change_24h' ? '% Change' : 'Score'}
                  </span>
                </button>
              </div>
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
                      <span className="text-xs text-gray-500">{changePeriod}</span>
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
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
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
                  <div className="bg-gray-700/50 p-4 rounded-lg">
                    <div className="text-xs text-gray-400 mb-1 flex items-center gap-1">
                      <Search className="w-3 h-3" />
                      Search Interest
                    </div>
                    <div className="text-xl font-bold text-cyan-400">
                      {selectedPlayer.search_trends ? selectedPlayer.search_trends.search_interest.toFixed(0) : 'N/A'}
                    </div>
                  </div>
                </div>
              </motion.div>

              {/* Tabs */}
              <div className="bg-gray-800 rounded-xl">
                <div className="flex border-b border-gray-700">
                  {(['overview', 'social', 'media', 'trends', 'alerts'] as const).map((tab) => (
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
                      {loadingSocial ? (
                        <div className="bg-gray-700/30 p-4 rounded-lg text-center py-8">
                          <MessageSquare className="w-12 h-12 mx-auto mb-3 text-gray-600 animate-pulse" />
                          <p className="text-gray-400">Loading social mentions...</p>
                        </div>
                      ) : socialMentions.length > 0 ? (
                        socialMentions.map((mention) => (
                          <a
                            key={mention.id}
                            href={mention.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="block bg-gray-700/30 p-4 rounded-lg hover:bg-gray-700/50 transition-all hover:scale-[1.01] cursor-pointer group"
                          >
                            <div className="flex items-center gap-2 mb-3">
                              {getPlatformIcon(mention.platform)}
                              <span className={`font-medium text-sm ${getPlatformColor(mention.platform)}`}>
                                {mention.platform.charAt(0).toUpperCase() + mention.platform.slice(1)}
                              </span>
                              <span className="text-gray-500 text-sm">@{mention.author_handle}</span>
                              <span className="ml-auto text-xs text-gray-500">
                                {new Date(mention.posted_at).toLocaleDateString()}
                              </span>
                              <ExternalLink className="w-3 h-3 text-gray-600 group-hover:text-purple-400 transition-colors" />
                            </div>
                            <p className="text-sm text-gray-300 mb-3 leading-relaxed group-hover:text-white transition-colors">
                              {mention.content}
                            </p>
                            <div className="flex items-center gap-4 text-xs text-gray-500">
                              <div className="flex items-center gap-1">
                                <Heart className="w-3 h-3" />
                                <span>{mention.likes.toLocaleString()}</span>
                              </div>
                              <div className="flex items-center gap-1">
                                <Share2 className="w-3 h-3" />
                                <span>{mention.shares.toLocaleString()}</span>
                              </div>
                              <span className={`ml-auto px-2 py-0.5 rounded-full text-xs ${
                                mention.sentiment === 'positive' ? 'bg-green-500/20 text-green-400' :
                                mention.sentiment === 'negative' ? 'bg-red-500/20 text-red-400' :
                                'bg-gray-500/20 text-gray-400'
                              }`}>
                                {mention.sentiment}
                              </span>
                            </div>
                          </a>
                        ))
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
                      {loadingMedia ? (
                        <div className="bg-gray-700/30 p-4 rounded-lg text-center py-8">
                          <Newspaper className="w-12 h-12 mx-auto mb-3 text-gray-600 animate-pulse" />
                          <p className="text-gray-400">Loading media articles...</p>
                        </div>
                      ) : mediaArticles.length > 0 ? (
                        mediaArticles.map((article) => (
                          <a
                            key={article.id}
                            href={article.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="block bg-gray-700/30 p-4 rounded-lg hover:bg-gray-700/50 transition-all hover:scale-[1.01] cursor-pointer group"
                          >
                            <div className="flex items-center gap-2 mb-3">
                              <Newspaper className="w-4 h-4 text-blue-400" />
                              <span className="font-medium text-sm text-blue-400">
                                {article.source}
                              </span>
                              <span className="ml-auto text-xs text-gray-500">
                                {new Date(article.published_at).toLocaleDateString()}
                              </span>
                              <ExternalLink className="w-3 h-3 text-gray-600 group-hover:text-purple-400 transition-colors" />
                            </div>
                            <h4 className="text-md font-medium text-white mb-2 group-hover:text-purple-300 transition-colors">
                              {article.title}
                            </h4>
                            <p className="text-sm text-gray-400 mb-3 leading-relaxed line-clamp-3">
                              {article.summary}
                            </p>
                            <div className="flex items-center gap-4">
                              <span className={`px-2 py-0.5 rounded-full text-xs ${
                                article.sentiment === 'positive' ? 'bg-green-500/20 text-green-400' :
                                article.sentiment === 'negative' ? 'bg-red-500/20 text-red-400' :
                                'bg-gray-500/20 text-gray-400'
                              }`}>
                                {article.sentiment}
                              </span>
                            </div>
                          </a>
                        ))
                      ) : (
                        <div className="bg-gray-700/30 p-4 rounded-lg text-center py-8">
                          <Newspaper className="w-12 h-12 mx-auto mb-3 text-gray-600" />
                          <p className="text-gray-400">No recent media coverage found</p>
                          <p className="text-xs text-gray-500 mt-2">
                            RSS feed collection runs every 2 hours
                          </p>
                        </div>
                      )}
                    </div>
                  )}

                  {activeTab === 'trends' && (
                    <div className="space-y-4">
                      {selectedPlayer.search_trends ? (
                        <>
                          {/* Google Trends Summary */}
                          <div className="bg-gray-700/30 p-4 rounded-lg">
                            <h4 className="font-medium mb-3 flex items-center gap-2">
                              <Search className="w-5 h-5 text-cyan-400" />
                              Google Search Trends
                            </h4>
                            <div className="grid grid-cols-3 gap-4 mb-4">
                              <div className="bg-gray-800/50 p-3 rounded">
                                <div className="text-xs text-gray-400 mb-1">Current Interest</div>
                                <div className="text-2xl font-bold text-cyan-400">
                                  {selectedPlayer.search_trends.search_interest.toFixed(0)}
                                </div>
                                <div className="text-xs text-gray-500">out of 100</div>
                              </div>
                              <div className="bg-gray-800/50 p-3 rounded">
                                <div className="text-xs text-gray-400 mb-1">7-Day Average</div>
                                <div className="text-2xl font-bold text-blue-400">
                                  {selectedPlayer.search_trends.search_interest_avg_7d.toFixed(1)}
                                </div>
                              </div>
                              <div className="bg-gray-800/50 p-3 rounded">
                                <div className="text-xs text-gray-400 mb-1">Growth Rate</div>
                                <div className={`text-2xl font-bold ${selectedPlayer.search_trends.growth_rate > 0 ? 'text-green-400' : 'text-red-400'}`}>
                                  {selectedPlayer.search_trends.growth_rate > 0 ? '+' : ''}
                                  {selectedPlayer.search_trends.growth_rate.toFixed(1)}%
                                </div>
                              </div>
                            </div>
                            <p className="text-sm text-gray-400">
                              Search interest shows how frequently people are searching for{' '}
                              <span className="text-white font-medium">{selectedPlayer.player_name}</span> on Google.
                              {selectedPlayer.search_trends.growth_rate > 10 ? (
                                <span className="text-green-400"> This player is trending upward, indicating growing public interest.</span>
                              ) : selectedPlayer.search_trends.growth_rate < -10 ? (
                                <span className="text-red-400"> Search interest is declining.</span>
                              ) : (
                                <span className="text-gray-300"> Search interest is relatively stable.</span>
                              )}
                            </p>
                          </div>

                          {/* Related Queries */}
                          {selectedPlayer.search_trends.related_queries && selectedPlayer.search_trends.related_queries.length > 0 && (
                            <div className="bg-gray-700/30 p-4 rounded-lg">
                              <h4 className="font-medium mb-3">Related Search Queries</h4>
                              <div className="space-y-2">
                                {selectedPlayer.search_trends.related_queries.map((query, idx) => (
                                  <div key={idx} className="flex items-center justify-between bg-gray-800/50 p-2 rounded">
                                    <span className="text-sm text-gray-300">{query.query}</span>
                                    <span className="text-xs text-gray-500">Interest: {query.value}</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Rising Queries */}
                          {selectedPlayer.search_trends.rising_queries && selectedPlayer.search_trends.rising_queries.length > 0 && (
                            <div className="bg-gray-700/30 p-4 rounded-lg">
                              <h4 className="font-medium mb-3 flex items-center gap-2">
                                <TrendingUp className="w-5 h-5 text-green-400" />
                                Rising Searches (Breakout Topics)
                              </h4>
                              <div className="space-y-2">
                                {selectedPlayer.search_trends.rising_queries.map((query, idx) => (
                                  <div key={idx} className="flex items-center justify-between bg-gray-800/50 p-2 rounded">
                                    <span className="text-sm text-gray-300">{query.query}</span>
                                    <span className={`text-xs px-2 py-0.5 rounded ${
                                      query.value === 'Breakout' ? 'bg-green-500/20 text-green-400' : 'bg-blue-500/20 text-blue-400'
                                    }`}>
                                      {query.value}
                                    </span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Regional Interest */}
                          {selectedPlayer.search_trends.regional_interest && Object.keys(selectedPlayer.search_trends.regional_interest).length > 0 && (
                            <div className="bg-gray-700/30 p-4 rounded-lg">
                              <h4 className="font-medium mb-3">Top Regions by Search Interest</h4>
                              <div className="space-y-2">
                                {Object.entries(selectedPlayer.search_trends.regional_interest)
                                  .slice(0, 5)
                                  .map(([region, interest], idx) => (
                                    <div key={idx} className="flex items-center gap-3">
                                      <span className="text-sm text-gray-300 w-32">{region}</span>
                                      <div className="flex-1 h-6 bg-gray-800 rounded-full overflow-hidden">
                                        <div
                                          className="h-full bg-gradient-to-r from-cyan-500 to-blue-500"
                                          style={{ width: `${interest}%` }}
                                        />
                                      </div>
                                      <span className="text-xs text-gray-500 w-10 text-right">{interest}</span>
                                    </div>
                                  ))}
                              </div>
                            </div>
                          )}

                          {/* Data Collection Info */}
                          <div className="text-xs text-gray-500 text-center">
                            Last updated: {new Date(selectedPlayer.search_trends.collected_at).toLocaleString()}
                          </div>
                        </>
                      ) : (
                        <div className="bg-gray-700/30 p-4 rounded-lg text-center py-8">
                          <Search className="w-12 h-12 mx-auto mb-3 text-gray-600" />
                          <p className="text-gray-400">No Google Trends data available</p>
                          <p className="text-xs text-gray-500 mt-2">
                            Google Trends data is collected periodically for players with hype scores
                          </p>
                        </div>
                      )}
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