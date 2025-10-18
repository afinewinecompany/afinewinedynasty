'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import DashboardTile from './DashboardTile';
import {
  Home,
  TrendingUp,
  Users,
  Trophy,
  Activity,
  Search,
  BarChart,
  Zap,
  BookOpen,
  ChevronRight,
  X
} from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { useProspects } from '@/hooks/useProspects';
import Link from 'next/link';

export default function Dashboard() {
  const router = useRouter();
  const { user } = useAuth();
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [leagueStats, setLeagueStats] = useState<any>(null);

  // Fetch top prospects for the snapshot tile
  const { data: topProspects, loading: prospectsLoading } = useProspects({
    page: 1,
    limit: 5,
    sort_by: 'name',
    sort_order: 'asc',
  });

  // Check if first-time user
  useEffect(() => {
    const hasSeenOnboarding = localStorage.getItem('hasSeenOnboarding');
    if (!hasSeenOnboarding) {
      setShowOnboarding(true);
    }
  }, []);

  const dismissOnboarding = () => {
    setShowOnboarding(false);
    localStorage.setItem('hasSeenOnboarding', 'true');
  };

  return (
    <div className="min-h-screen bg-gray-50 p-4 md:p-6">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-gray-900 mb-2">
          Dynasty League Command Center
        </h1>
        <p className="text-lg text-gray-600">
          Welcome back{user?.name ? `, ${user.name}` : ''}! Your complete hub for dynasty league management.
        </p>
      </div>

      {/* Onboarding/Welcome Tile - Collapsible */}
      {showOnboarding && (
        <div className="mb-6 bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg p-6">
          <div className="flex justify-between items-start">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-3">
                <BookOpen className="w-6 h-6 text-blue-600" />
                <h2 className="text-xl font-semibold text-gray-900">
                  Welcome to A Fine Wine Dynasty!
                </h2>
              </div>
              <p className="text-gray-700 mb-4">
                Your ultimate tool for dominating dynasty fantasy baseball. Here's how to get started:
              </p>
              <div className="grid md:grid-cols-3 gap-4">
                <div className="bg-white/70 rounded p-3">
                  <h3 className="font-semibold text-sm mb-1">1. Set Up Your League</h3>
                  <p className="text-sm text-gray-600">
                    Connect your league and import your roster
                  </p>
                </div>
                <div className="bg-white/70 rounded p-3">
                  <h3 className="font-semibold text-sm mb-1">2. Explore Rankings</h3>
                  <p className="text-sm text-gray-600">
                    View ML-powered prospect rankings and analysis
                  </p>
                </div>
                <div className="bg-white/70 rounded p-3">
                  <h3 className="font-semibold text-sm mb-1">3. Optimize Lineups</h3>
                  <p className="text-sm text-gray-600">
                    Get AI recommendations for your daily lineups
                  </p>
                </div>
              </div>
            </div>
            <button
              onClick={dismissOnboarding}
              className="ml-4 text-gray-500 hover:text-gray-700"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>
      )}

      {/* Dashboard Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">

        {/* League Overview Tile */}
        <DashboardTile
          title="League Overview"
          icon={Trophy}
          action={{
            label: 'View Details',
            onClick: () => router.push('/my-league')
          }}
        >
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">Active League</span>
              <span className="text-sm font-medium">
                {user?.activeLeague || 'No league selected'}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">Your Standing</span>
              <span className="text-sm font-medium">-</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">Roster Size</span>
              <span className="text-sm font-medium">-</span>
            </div>
            <Link
              href="/my-league"
              className="block mt-4 text-center py-2 px-4 bg-blue-50 text-blue-600 rounded hover:bg-blue-100 transition-colors"
            >
              Manage League Settings
            </Link>
          </div>
        </DashboardTile>

        {/* Top Prospects Snapshot */}
        <DashboardTile
          title="Top Prospects"
          icon={TrendingUp}
          action={{
            label: 'View All',
            onClick: () => router.push('/prospects')
          }}
          isLoading={prospectsLoading}
        >
          <div className="space-y-2">
            {topProspects?.prospects?.slice(0, 5).map((prospect: any, index: number) => (
              <Link
                key={prospect.id}
                href={`/prospects/${prospect.id}`}
                className="flex items-center justify-between p-2 hover:bg-gray-50 rounded transition-colors"
              >
                <div className="flex items-center gap-3">
                  <span className="text-sm font-bold text-gray-500">
                    #{index + 1}
                  </span>
                  <div>
                    <p className="text-sm font-medium text-gray-900">
                      {prospect.name}
                    </p>
                    <p className="text-xs text-gray-500">
                      {prospect.position} • {prospect.organization}
                    </p>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-gray-400" />
              </Link>
            ))}
          </div>
        </DashboardTile>

        {/* HYPE Leaderboard Preview */}
        <DashboardTile
          title="HYPE Leaders"
          icon={Zap}
          action={{
            label: 'Full Leaderboard',
            onClick: () => router.push('/hype')
          }}
        >
          <div className="space-y-2">
            <div className="text-center py-4 text-sm text-gray-500">
              <p>Track weekly performance</p>
              <p>and momentum shifts</p>
            </div>
            <Link
              href="/hype"
              className="block text-center py-2 px-4 bg-green-50 text-green-600 rounded hover:bg-green-100 transition-colors"
            >
              View HYPE Scores
            </Link>
          </div>
        </DashboardTile>

        {/* Roster Health */}
        <DashboardTile
          title="Roster Health"
          icon={Users}
          action={{
            label: 'Manage Roster',
            onClick: () => router.push('/my-league')
          }}
        >
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">Active Players</span>
              <span className="text-sm font-medium">-</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">IL/Injured</span>
              <span className="text-sm font-medium text-red-600">-</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">Prospects</span>
              <span className="text-sm font-medium text-green-600">-</span>
            </div>
            <div className="pt-2 border-t">
              <p className="text-xs text-gray-500 text-center">
                Connect your league for roster insights
              </p>
            </div>
          </div>
        </DashboardTile>

        {/* Recent Activity */}
        <DashboardTile
          title="Recent Activity"
          icon={Activity}
        >
          <div className="space-y-2">
            <div className="text-center py-4 text-sm text-gray-500">
              <p>Your recent searches,</p>
              <p>views, and comparisons</p>
              <p>will appear here</p>
            </div>
          </div>
        </DashboardTile>

        {/* Quick Actions */}
        <DashboardTile
          title="Quick Actions"
          icon={BarChart}
        >
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => router.push('/prospects')}
              className="p-3 text-sm bg-blue-50 text-blue-700 rounded hover:bg-blue-100 transition-colors font-medium"
            >
              View Rankings
            </button>
            <button
              onClick={() => router.push('/compare')}
              className="p-3 text-sm bg-green-50 text-green-700 rounded hover:bg-green-100 transition-colors font-medium"
            >
              Compare Players
            </button>
            <button
              onClick={() => router.push('/lineups')}
              className="p-3 text-sm bg-purple-50 text-purple-700 rounded hover:bg-purple-100 transition-colors font-medium"
            >
              Set Lineups
            </button>
            <button
              onClick={() => router.push('/search/advanced')}
              className="p-3 text-sm bg-orange-50 text-orange-700 rounded hover:bg-orange-100 transition-colors font-medium"
            >
              Advanced Search
            </button>
          </div>
        </DashboardTile>

      </div>

      {/* Feature Highlights Section */}
      <div className="mt-12 bg-white rounded-lg shadow-sm border border-gray-200 p-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-6">
          Platform Features
        </h2>
        <div className="grid md:grid-cols-3 gap-6">
          <div>
            <h3 className="font-semibold text-gray-900 mb-2 flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-blue-600" />
              ML-Powered Rankings
            </h3>
            <p className="text-sm text-gray-600">
              Advanced machine learning models analyze player performance and project future value
            </p>
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 mb-2 flex items-center gap-2">
              <Users className="w-5 h-5 text-green-600" />
              Dynasty Focused
            </h3>
            <p className="text-sm text-gray-600">
              Specialized tools and analysis designed specifically for dynasty league formats
            </p>
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 mb-2 flex items-center gap-2">
              <Search className="w-5 h-5 text-purple-600" />
              Advanced Analytics
            </h3>
            <p className="text-sm text-gray-600">
              Deep statistical analysis with custom metrics tailored for dynasty success
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}