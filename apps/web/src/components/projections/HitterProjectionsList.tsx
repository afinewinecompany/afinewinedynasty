'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import HitterProjectionCard from './HitterProjectionCard';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';

interface Prospect {
  id: number;
  name: string;
  position: string;
}

interface ProspectsResponse {
  prospects: Prospect[];
  total: number;
}

export default function HitterProjectionsList() {
  const [positionFilter, setPositionFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<'name' | 'position'>('name');

  // Fetch all hitter prospects
  const {
    data: prospectsData,
    isLoading,
    error,
  } = useQuery<ProspectsResponse>({
    queryKey: ['hitter-prospects'],
    queryFn: async () => {
      // Fetch hitters only (exclude pitchers)
      // Note: Trailing slash required to avoid 307 redirect from FastAPI
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/prospects/?position_type=hitter&limit=200`
      );
      if (!res.ok) throw new Error('Failed to fetch prospects');
      return res.json();
    },
  });

  // Filter and sort prospects
  const filteredProspects = prospectsData?.prospects
    ?.filter((p) => {
      if (positionFilter !== 'all' && p.position !== positionFilter) return false;
      if (searchQuery && !p.name.toLowerCase().includes(searchQuery.toLowerCase()))
        return false;
      return true;
    })
    .sort((a, b) => {
      if (sortBy === 'name') {
        return a.name.localeCompare(b.name);
      }
      return a.position.localeCompare(b.position);
    });

  const positions = ['C', 'IF', 'SS', '2B', '3B', 'OF', 'Corner', 'DH'];

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="flex gap-4 mb-6">
          <div className="h-10 bg-wine-plum/50 rounded w-64 animate-pulse"></div>
          <div className="h-10 bg-wine-plum/50 rounded w-48 animate-pulse"></div>
          <div className="h-10 bg-wine-plum/50 rounded w-48 animate-pulse"></div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[...Array(9)].map((_, i) => (
            <div
              key={i}
              className="h-64 bg-wine-plum/50 rounded-lg animate-pulse"
            ></div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-wine-dark/50 rounded-lg border border-wine-periwinkle/20 p-12 text-center">
        <h3 className="text-xl font-bold text-red-400 mb-2">
          Failed to Load Prospects
        </h3>
        <p className="text-wine-periwinkle/70">
          {error instanceof Error ? error.message : 'An error occurred'}
        </p>
      </div>
    );
  }

  return (
    <div>
      {/* Filters and Controls */}
      <div className="flex flex-wrap gap-4 mb-6">
        {/* Search */}
        <Input
          type="text"
          placeholder="Search by name..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="max-w-xs bg-wine-dark/50 border-wine-periwinkle/20 text-white placeholder:text-wine-periwinkle/50"
        />

        {/* Position Filter */}
        <select
          value={positionFilter}
          onChange={(e) => setPositionFilter(e.target.value)}
          className="px-4 py-2 bg-wine-dark/50 border border-wine-periwinkle/20 rounded-md text-white focus:outline-none focus:ring-2 focus:ring-wine-periwinkle"
        >
          <option value="all">All Positions</option>
          {positions.map((pos) => (
            <option key={pos} value={pos}>
              {pos}
            </option>
          ))}
        </select>

        {/* Sort By */}
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as 'name' | 'position')}
          className="px-4 py-2 bg-wine-dark/50 border border-wine-periwinkle/20 rounded-md text-white focus:outline-none focus:ring-2 focus:ring-wine-periwinkle"
        >
          <option value="name">Sort by Name</option>
          <option value="position">Sort by Position</option>
        </select>

        {/* Results Count */}
        <div className="flex items-center text-wine-periwinkle/70 ml-auto">
          {filteredProspects?.length || 0} prospects
        </div>
      </div>

      {/* Results */}
      {filteredProspects && filteredProspects.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredProspects.map((prospect) => (
            <HitterProjectionCard
              key={prospect.id}
              prospectId={prospect.id}
            />
          ))}
        </div>
      ) : (
        <div className="bg-wine-dark/50 rounded-lg border border-wine-periwinkle/20 p-12 text-center">
          <p className="text-wine-periwinkle/70">
            No prospects found matching your filters.
          </p>
        </div>
      )}

      {/* Info Note */}
      {filteredProspects && filteredProspects.length > 0 && (
        <div className="mt-8 bg-wine-dark/30 rounded-lg p-4 border border-wine-periwinkle/20">
          <p className="text-wine-periwinkle/70 text-sm">
            Showing projections for hitters with sufficient MiLB performance data. Not all
            prospects have projections available due to limited historical data or
            incomplete stats.
          </p>
        </div>
      )}
    </div>
  );
}
