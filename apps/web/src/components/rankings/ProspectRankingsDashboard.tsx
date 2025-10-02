'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useProspectRankings } from '@/hooks/useProspectRankings';
import { useProspectSearch } from '@/hooks/useProspectSearch';
import ProspectRankingsTable from '../ui/ProspectRankingsTable';
import FilterPanel from '../ui/FilterPanel';
import SearchBar from '../ui/SearchBar';
import PaginationControls from '../ui/PaginationControls';
import { ProspectCard } from '../ui/ProspectCard';
import { Button } from '../ui/button';
import { Download, Filter, X } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { exportProspectsCsv } from '@/lib/api/prospects';

interface FilterState {
  position: string[];
  organization: string[];
  level: string[];
  etaMin?: number;
  etaMax?: number;
  ageMin?: number;
  ageMax?: number;
  search?: string;
}

interface SortState {
  sortBy: string;
  sortOrder: 'asc' | 'desc';
}

export default function ProspectRankingsDashboard() {
  const { user } = useAuth();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [filters, setFilters] = useState<FilterState>({
    position: [],
    organization: [],
    level: [],
  });
  const [sortState, setSortState] = useState<SortState>({
    sortBy: 'dynasty_rank',
    sortOrder: 'asc',
  });
  const [searchQuery, setSearchQuery] = useState('');
  const [isMobileFilterOpen, setIsMobileFilterOpen] = useState(false);
  const [isExporting, setIsExporting] = useState(false);

  // Fetch rankings data
  const { data, isLoading, error, refetch } = useProspectRankings({
    page,
    pageSize,
    ...filters,
    search: searchQuery,
    ...sortState,
  });

  // Search autocomplete hook
  const { suggestions, getSuggestions } = useProspectSearch();

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
      level: [],
    });
    setSearchQuery('');
    setPage(1);
  }, []);

  // Handle CSV export
  const handleExport = async () => {
    if (!user || user.subscriptionTier !== 'premium') {
      alert('CSV export is only available for premium subscribers');
      return;
    }

    setIsExporting(true);
    try {
      await exportProspectsCsv({
        ...filters,
        search: searchQuery,
      });
    } catch (error) {
      console.error('Export failed:', error);
      alert('Failed to export CSV. Please try again.');
    } finally {
      setIsExporting(false);
    }
  };

  // Check if any filters are active
  const hasActiveFilters = useMemo(() => {
    return (
      filters.position.length > 0 ||
      filters.organization.length > 0 ||
      filters.level.length > 0 ||
      filters.etaMin !== undefined ||
      filters.etaMax !== undefined ||
      filters.ageMin !== undefined ||
      filters.ageMax !== undefined ||
      searchQuery.length > 0
    );
  }, [filters, searchQuery]);

  // Mobile breakpoint check
  const isMobile = typeof window !== 'undefined' && window.innerWidth < 768;

  return (
    <div className="prospect-rankings-dashboard">
      {/* Header */}
      <div className="dashboard-header mb-6">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">
              Prospect Rankings
            </h1>
            <p className="mt-2 text-gray-600">
              Top 500 dynasty prospects with ML-powered rankings
            </p>
          </div>

          <div className="flex gap-3">
            {user?.subscriptionTier === 'premium' && (
              <Button
                onClick={handleExport}
                disabled={isExporting}
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
          onSuggestionsFetch={getSuggestions}
          suggestions={suggestions}
          placeholder="Search prospects by name or organization..."
        />
      </div>

      {/* Active Filters Display */}
      {hasActiveFilters && (
        <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="flex items-center justify-between">
            <span className="text-sm text-blue-800 font-medium">
              Active Filters: {data?.total || 0} results
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
          {isLoading ? (
            <div className="flex items-center justify-center h-64">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            </div>
          ) : error ? (
            <div className="text-center py-12">
              <p className="text-red-600">
                Failed to load rankings. Please try again.
              </p>
              <Button onClick={() => refetch()} className="mt-4">
                Retry
              </Button>
            </div>
          ) : data?.prospects && data.prospects.length > 0 ? (
            <>
              {/* Desktop Table View */}
              {!isMobile ? (
                <ProspectRankingsTable
                  prospects={data.prospects}
                  sortBy={sortState.sortBy}
                  sortOrder={sortState.sortOrder}
                  onSort={handleSortChange}
                />
              ) : (
                // Mobile Card View
                <div className="space-y-3">
                  {data.prospects.map((prospect) => (
                    <ProspectCard
                      key={prospect.id}
                      prospect={prospect}
                      showRanking
                      showConfidence
                    />
                  ))}
                </div>
              )}

              {/* Pagination */}
              <div className="mt-6">
                <PaginationControls
                  page={page}
                  pageSize={pageSize}
                  total={data.total}
                  totalPages={data.totalPages}
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
