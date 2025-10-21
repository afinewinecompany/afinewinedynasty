'use client';

import React, { useState, useCallback, useMemo } from 'react';
import { useCompositeRankings } from '@/hooks/useCompositeRankings';
import CompositeRankingsTable from './CompositeRankingsTable';
import CompositeRankingsCard from './CompositeRankingsCard';
import FilterPanel from '../ui/FilterPanel';
import SearchBar from '../ui/SearchBar';
import PaginationControls from '../ui/PaginationControls';
import { Button } from '../ui/button';
import { Filter, X, Download, Info } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

interface FilterState {
  position: string[];
  organization: string[];
}

interface SortState {
  sortBy: string;
  sortOrder: 'asc' | 'desc';
}

export default function CompositeRankingsDashboard() {
  const { user } = useAuth();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [filters, setFilters] = useState<FilterState>({
    position: [],
    organization: [],
  });
  const [sortState, setSortState] = useState<SortState>({
    sortBy: 'rank',
    sortOrder: 'asc',
  });
  const [searchQuery, setSearchQuery] = useState('');
  const [isMobileFilterOpen, setIsMobileFilterOpen] = useState(false);

  // Fetch composite rankings data
  const { data, loading, error, refetch } = useCompositeRankings({
    page,
    page_size: pageSize,
    position: filters.position.length > 0 ? filters.position[0] : undefined,
    organization: filters.organization.length > 0 ? filters.organization[0] : undefined,
    limit: user?.subscriptionTier === 'premium' ? 500 : 100,
  });

  // Handle filter changes
  const handleFilterChange = useCallback((newFilters: Partial<FilterState>) => {
    setFilters((prev) => ({ ...prev, ...newFilters }));
    setPage(1); // Reset to first page on filter change
  }, []);

  // Handle sort changes
  const handleSortChange = useCallback((column: string) => {
    setSortState((prev) => ({
      sortBy: column,
      sortOrder:
        prev.sortBy === column && prev.sortOrder === 'asc' ? 'desc' : 'asc',
    }));
  }, []);

  // Handle search
  const handleSearch = useCallback((query: string) => {
    setSearchQuery(query);
    setPage(1); // Reset to first page on search
  }, []);

  // Handle clear filters
  const clearFilters = useCallback(() => {
    setFilters({
      position: [],
      organization: [],
    });
    setSearchQuery('');
    setPage(1);
  }, []);

  // Check if any filters are active
  const hasActiveFilters = useMemo(() => {
    return (
      filters.position.length > 0 ||
      filters.organization.length > 0 ||
      searchQuery.length > 0
    );
  }, [filters, searchQuery]);

  // Filter and sort data client-side for better UX
  const filteredAndSortedProspects = useMemo(() => {
    if (!data?.prospects) return [];

    let prospects = [...data.prospects];

    // Client-side search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      prospects = prospects.filter(
        (p) =>
          p.name.toLowerCase().includes(query) ||
          p.organization?.toLowerCase().includes(query)
      );
    }

    // Client-side sorting
    prospects.sort((a, b) => {
      let aVal: any = a[sortState.sortBy as keyof typeof a];
      let bVal: any = b[sortState.sortBy as keyof typeof b];

      // Handle null/undefined
      if (aVal === null || aVal === undefined) aVal = sortState.sortOrder === 'asc' ? Infinity : -Infinity;
      if (bVal === null || bVal === undefined) bVal = sortState.sortOrder === 'asc' ? Infinity : -Infinity;

      // String comparison
      if (typeof aVal === 'string' && typeof bVal === 'string') {
        return sortState.sortOrder === 'asc'
          ? aVal.localeCompare(bVal)
          : bVal.localeCompare(aVal);
      }

      // Numeric comparison
      return sortState.sortOrder === 'asc' ? aVal - bVal : bVal - aVal;
    });

    return prospects;
  }, [data?.prospects, searchQuery, sortState]);

  // Mobile breakpoint check
  const isMobile = typeof window !== 'undefined' && window.innerWidth < 768;

  return (
    <div className="composite-rankings-dashboard">
      {/* Header */}
      <div className="dashboard-header mb-6">
        <div className="flex justify-between items-start">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-bold text-gray-900">
                Composite Rankings
              </h1>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger>
                    <Info className="w-5 h-5 text-gray-400 hover:text-gray-600 transition-colors" />
                  </TooltipTrigger>
                  <TooltipContent className="bg-popover border-border max-w-md">
                    <div className="text-sm text-popover-foreground">
                      <p className="font-semibold mb-2">How Composite Rankings Work</p>
                      <p className="mb-2">
                        Combines FanGraphs expert grades with real-time MiLB performance data:
                      </p>
                      <ul className="space-y-1 text-xs">
                        <li>• Base FV: FanGraphs Future Value (40-70 scale)</li>
                        <li>• Performance: Recent stats vs level peers (±10)</li>
                        <li>• Trend: 30-day hot/cold streaks (±5)</li>
                        <li>• Age: Age-relative-to-level bonus/penalty (±5)</li>
                      </ul>
                    </div>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
            <p className="mt-2 text-gray-600">
              {user?.subscriptionTier === 'premium'
                ? 'Dynamic rankings combining FanGraphs grades with MiLB performance (Top 500)'
                : 'Dynamic rankings combining FanGraphs grades with MiLB performance (Top 100 - Upgrade for full access)'}
            </p>
          </div>

          <div className="flex gap-3">
            {user?.subscriptionTier === 'premium' && (
              <Button
                onClick={() => {
                  // TODO: Implement CSV export
                  alert('CSV export coming soon!');
                }}
                className="flex items-center gap-2"
                variant="secondary"
              >
                <Download className="w-4 h-4" />
                Export CSV
              </Button>
            )}

            {isMobile && (
              <Button
                onClick={() => setIsMobileFilterOpen(!isMobileFilterOpen)}
                variant="outline"
                className="flex items-center gap-2"
              >
                <Filter className="w-4 h-4" />
                Filters
                {hasActiveFilters && (
                  <span className="ml-1 px-2 py-0.5 text-xs bg-blue-100 text-blue-800 rounded-full">
                    Active
                  </span>
                )}
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Search Bar */}
      <div className="mb-4">
        <SearchBar
          value={searchQuery}
          onChange={handleSearch}
          placeholder="Search prospects by name or organization..."
        />
      </div>

      {/* Active Filters Display */}
      {hasActiveFilters && (
        <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="flex items-center justify-between">
            <span className="text-sm text-blue-800 font-medium">
              Active Filters: {filteredAndSortedProspects.length} results
            </span>
            <Button
              onClick={clearFilters}
              variant="ghost"
              size="sm"
              className="text-blue-600 hover:text-blue-800"
            >
              <X className="w-4 h-4 mr-1" />
              Clear All
            </Button>
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex gap-6">
        {/* Desktop Filter Panel */}
        {!isMobile && (
          <div className="w-64 flex-shrink-0">
            <FilterPanel
              filters={filters}
              onChange={handleFilterChange}
              onClear={clearFilters}
            />
          </div>
        )}

        {/* Rankings Table/Cards */}
        <div className="flex-1">
          {loading ? (
            <div className="flex items-center justify-center h-64">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            </div>
          ) : error ? (
            <div className="text-center py-12">
              <p className="text-red-600">
                Failed to load composite rankings. Please try again.
              </p>
              <Button onClick={() => refetch()} className="mt-4">
                Retry
              </Button>
            </div>
          ) : filteredAndSortedProspects.length > 0 ? (
            <>
              {/* Desktop Table View */}
              {!isMobile ? (
                <CompositeRankingsTable
                  prospects={filteredAndSortedProspects}
                  sortBy={sortState.sortBy}
                  sortOrder={sortState.sortOrder}
                  onSort={handleSortChange}
                />
              ) : (
                // Mobile Card View
                <div className="space-y-3">
                  {filteredAndSortedProspects.map((prospect) => (
                    <CompositeRankingsCard
                      key={prospect.prospect_id}
                      prospect={prospect}
                    />
                  ))}
                </div>
              )}

              {/* Pagination */}
              <div className="mt-6">
                <PaginationControls
                  page={page}
                  pageSize={pageSize}
                  total={data?.total || 0}
                  totalPages={data?.total_pages || 0}
                  onPageChange={setPage}
                  onPageSizeChange={(size) => {
                    setPageSize(size);
                    setPage(1);
                  }}
                />
              </div>
            </>
          ) : (
            <div className="text-center py-12">
              <p className="text-gray-600">
                No prospects found matching your criteria.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Mobile Filter Bottom Sheet */}
      {isMobile && isMobileFilterOpen && (
        <div className="fixed inset-0 z-50 bg-black bg-opacity-50">
          <div className="fixed bottom-0 left-0 right-0 bg-white rounded-t-xl p-6 max-h-[80vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-semibold">Filters</h2>
              <Button
                onClick={() => setIsMobileFilterOpen(false)}
                variant="ghost"
                size="sm"
              >
                <X className="w-5 h-5" />
              </Button>
            </div>

            <FilterPanel
              filters={filters}
              onChange={handleFilterChange}
              onClear={clearFilters}
              mobile
            />

            <div className="mt-6 flex gap-3">
              <Button
                onClick={() => setIsMobileFilterOpen(false)}
                className="flex-1"
              >
                Apply Filters
              </Button>
              <Button
                onClick={clearFilters}
                variant="outline"
                className="flex-1"
              >
                Clear All
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
