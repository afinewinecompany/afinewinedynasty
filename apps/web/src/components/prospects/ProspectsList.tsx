'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useProspects } from '@/hooks/useProspects';
import { ProspectListParams } from '@/types/prospect';
import LoadingSpinner from '@/components/ui/LoadingSpinner';
import ErrorMessage from '@/components/ui/ErrorMessage';
import SearchBar from '@/components/ui/SearchBar';
import FilterPanel from '@/components/ui/FilterPanel';
import Pagination from '@/components/ui/Pagination';
import ProspectCard from '@/components/ui/ProspectCard';

interface SortConfig {
  key: 'name' | 'age' | 'level' | 'organization';
  direction: 'asc' | 'desc';
}

export default function ProspectsList() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // Initialize state from URL parameters
  const [params, setParams] = useState<ProspectListParams>(() => {
    return {
      page: parseInt(searchParams.get('page') || '1'),
      limit: parseInt(searchParams.get('limit') || '25'),
      position: searchParams.get('position') || '',
      organization: searchParams.get('organization') || '',
      sort_by:
        (searchParams.get('sort_by') as
          | 'name'
          | 'age'
          | 'level'
          | 'organization') || 'name',
      sort_order: (searchParams.get('sort_order') as 'asc' | 'desc') || 'asc',
      search: searchParams.get('search') || '',
    };
  });

  const [searchInput, setSearchInput] = useState(params.search);
  const [isMobile, setIsMobile] = useState(false);
  const [sortConfig, setSortConfig] = useState<SortConfig>({
    key: params.sort_by as SortConfig['key'],
    direction: params.sort_order,
  });

  const { data, loading, error, refetch } = useProspects(params);

  // Update URL when params change
  useEffect(() => {
    const newSearchParams = new URLSearchParams();

    if (params.page !== 1) newSearchParams.set('page', params.page.toString());
    if (params.limit !== 25)
      newSearchParams.set('limit', params.limit.toString());
    if (params.position) newSearchParams.set('position', params.position);
    if (params.organization)
      newSearchParams.set('organization', params.organization);
    if (params.sort_by !== 'name')
      newSearchParams.set('sort_by', params.sort_by);
    if (params.sort_order !== 'asc')
      newSearchParams.set('sort_order', params.sort_order);
    if (params.search) newSearchParams.set('search', params.search);

    const newUrl = `/prospects${newSearchParams.toString() ? `?${newSearchParams.toString()}` : ''}`;
    router.replace(newUrl, { scroll: false });
  }, [params, router]);

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setParams((prev) => ({
        ...prev,
        search: searchInput,
        page: 1,
      }));
    }, 300);

    return () => clearTimeout(timer);
  }, [searchInput]);

  // Check if mobile on mount and resize
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };

    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  const handleSortChange = (key: SortConfig['key']) => {
    const direction =
      sortConfig.key === key && sortConfig.direction === 'asc' ? 'desc' : 'asc';

    setSortConfig({ key, direction });
    setParams((prev) => ({
      ...prev,
      sort_by: key,
      sort_order: direction,
      page: 1,
    }));
  };

  const handlePageChange = (page: number) => {
    setParams((prev) => ({ ...prev, page }));
  };

  const handlePositionChange = (position: string) => {
    setParams((prev) => ({ ...prev, position, page: 1 }));
  };

  const handleOrganizationChange = (organization: string) => {
    setParams((prev) => ({ ...prev, organization, page: 1 }));
  };

  const handleClearFilters = () => {
    setParams((prev) => ({
      ...prev,
      position: '',
      organization: '',
      page: 1,
    }));
  };

  const getSortIcon = (key: SortConfig['key']) => {
    if (sortConfig.key !== key) {
      return (
        <svg
          className="ml-1 h-4 w-4 text-gray-400"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M8 9l4-4 4 4m0 6l-4 4-4-4"
          />
        </svg>
      );
    }

    return sortConfig.direction === 'asc' ? (
      <svg
        className="ml-1 h-4 w-4 text-blue-600"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M5 15l7-7 7 7"
        />
      </svg>
    ) : (
      <svg
        className="ml-1 h-4 w-4 text-blue-600"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M19 9l-7 7-7-7"
        />
      </svg>
    );
  };

  if (error) {
    return (
      <div className="container mx-auto px-4 py-8">
        <ErrorMessage
          message={error}
          onRetry={refetch}
          className="mx-auto max-w-md"
        />
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          Prospect Rankings
        </h1>
        <p className="text-gray-600">
          Top 100 MLB prospects with detailed stats and analysis
        </p>
      </div>

      <div className="flex flex-col lg:flex-row gap-6">
        {/* Desktop Filter Panel */}
        {!isMobile && (
          <div className="w-full lg:w-64 flex-shrink-0">
            <FilterPanel
              selectedPosition={params.position || ''}
              selectedOrganization={params.organization || ''}
              onPositionChange={handlePositionChange}
              onOrganizationChange={handleOrganizationChange}
              onClearFilters={handleClearFilters}
            />
          </div>
        )}

        <div className="flex-1">
          {/* Search and Mobile Filters */}
          <div className="mb-6 flex flex-col sm:flex-row gap-4">
            <div className="flex-1">
              <SearchBar
                value={searchInput}
                onChange={setSearchInput}
                placeholder="Search prospects by name..."
                disabled={loading}
              />
            </div>
            {isMobile && (
              <div className="flex-shrink-0">
                <FilterPanel
                  selectedPosition={params.position || ''}
                  selectedOrganization={params.organization || ''}
                  onPositionChange={handlePositionChange}
                  onOrganizationChange={handleOrganizationChange}
                  onClearFilters={handleClearFilters}
                  isMobile={true}
                />
              </div>
            )}
          </div>

          {/* Loading State */}
          {loading && (
            <div className="flex justify-center py-12">
              <LoadingSpinner size="lg" />
            </div>
          )}

          {/* Results */}
          {!loading && data && (
            <>
              <div className="mb-4 text-sm text-gray-500">
                Showing {data.prospects.length} of {data.total} prospects
              </div>

              {/* Mobile Card View */}
              {isMobile ? (
                <div className="space-y-3">
                  {data.prospects.map((prospect, index) => (
                    <ProspectCard
                      key={prospect.id}
                      prospect={prospect}
                      rank={(data.page - 1) * data.limit + index + 1}
                    />
                  ))}
                </div>
              ) : (
                /* Desktop Table View */
                <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                            Rank
                          </th>
                          <th
                            className="cursor-pointer px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 hover:bg-gray-100"
                            onClick={() => handleSortChange('name')}
                          >
                            <div className="flex items-center">
                              Name
                              {getSortIcon('name')}
                            </div>
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                            Position
                          </th>
                          <th
                            className="cursor-pointer px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 hover:bg-gray-100"
                            onClick={() => handleSortChange('organization')}
                          >
                            <div className="flex items-center">
                              Organization
                              {getSortIcon('organization')}
                            </div>
                          </th>
                          <th
                            className="cursor-pointer px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 hover:bg-gray-100"
                            onClick={() => handleSortChange('level')}
                          >
                            <div className="flex items-center">
                              Level
                              {getSortIcon('level')}
                            </div>
                          </th>
                          <th
                            className="cursor-pointer px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 hover:bg-gray-100"
                            onClick={() => handleSortChange('age')}
                          >
                            <div className="flex items-center">
                              Age
                              {getSortIcon('age')}
                            </div>
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                            ETA
                          </th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-200 bg-white">
                        {data.prospects.map((prospect, index) => (
                          <tr key={prospect.id} className="hover:bg-gray-50">
                            <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-900">
                              #{(data.page - 1) * data.limit + index + 1}
                            </td>
                            <td className="whitespace-nowrap px-6 py-4 text-sm font-medium text-gray-900">
                              <Link
                                href={`/prospects/${prospect.id}`}
                                className="text-blue-600 hover:text-blue-800 hover:underline"
                              >
                                {prospect.name}
                              </Link>
                            </td>
                            <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                              {prospect.position}
                            </td>
                            <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                              {prospect.organization}
                            </td>
                            <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                              {prospect.level}
                            </td>
                            <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                              {prospect.age}
                            </td>
                            <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                              {prospect.eta_year || '-'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Pagination */}
              {data.total_pages > 1 && (
                <div className="mt-6">
                  <Pagination
                    currentPage={data.page}
                    totalPages={data.total_pages}
                    onPageChange={handlePageChange}
                    disabled={loading}
                  />
                </div>
              )}
            </>
          )}

          {/* No Results */}
          {!loading && data && data.prospects.length === 0 && (
            <div className="text-center py-12">
              <svg
                className="mx-auto h-12 w-12 text-gray-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
              <h3 className="mt-2 text-sm font-medium text-gray-900">
                No prospects found
              </h3>
              <p className="mt-1 text-sm text-gray-500">
                Try adjusting your search or filter criteria.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
