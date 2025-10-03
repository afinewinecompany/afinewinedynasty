'use client';

import { useState } from 'react';
import { AdvancedSearchForm } from '@/components/search/AdvancedSearchForm';
import { SavedSearches } from '@/components/search/SavedSearches';
import { SearchHistory } from '@/components/search/SearchHistory';
import { RecentlyViewedProspects } from '@/components/search/RecentlyViewedProspects';
import { SearchResults } from '@/components/search/SearchResults';
import { useAdvancedSearch } from '@/hooks/useAdvancedSearch';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Search, History, Bookmark, Eye } from 'lucide-react';

/**
 * Advanced Search Page Component
 *
 * Main page component providing a comprehensive search interface with dynamic
 * criteria builders, saved search management, search history, and recently
 * viewed prospects tracking. Serves as the primary entry point for complex
 * multi-criteria prospect searches.
 *
 * Features:
 * - Multi-criteria search form with collapsible sections (statistical, scouting, ML, timeline filters)
 * - Saved search management with create/edit/delete operations and quick execution
 * - Search history tracking with one-click re-execution of past searches
 * - Recently viewed prospects sidebar for research continuity
 * - Results display with relevance scoring and pagination
 * - Tabbed interface for organizing search, saved searches, and history
 * - Real-time search execution with loading states
 * - Error handling with user-friendly messages
 *
 * @page
 * @returns {JSX.Element} Advanced search page with tabbed interface
 *
 * @example
 * Access via route: /search/advanced
 *
 * @since 1.0.0
 * @version 3.4.0
 */
export default function AdvancedSearchPage() {
  const [activeTab, setActiveTab] = useState('search');
  const [selectedSavedSearch, setSelectedSavedSearch] = useState<any>(null);
  const {
    searchCriteria,
    searchResults,
    isLoading,
    error,
    executeSearch,
    updateCriteria,
    resetCriteria,
  } = useAdvancedSearch();

  const handleSavedSearchSelect = (savedSearch: any) => {
    setSelectedSavedSearch(savedSearch);
    updateCriteria(savedSearch.search_criteria);
    setActiveTab('search');
  };

  const handleHistoryItemSelect = (historyItem: any) => {
    if (historyItem.search_criteria) {
      updateCriteria(historyItem.search_criteria);
      setActiveTab('search');
    }
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          Advanced Search
        </h1>
        <p className="text-lg text-gray-600">
          Find prospects using sophisticated criteria combinations and discovery
          tools
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Main Search Interface */}
        <div className="lg:col-span-3">
          <Tabs
            value={activeTab}
            onValueChange={setActiveTab}
            className="w-full"
          >
            <TabsList className="grid w-full grid-cols-4">
              <TabsTrigger value="search" className="flex items-center gap-2">
                <Search className="h-4 w-4" />
                Search
              </TabsTrigger>
              <TabsTrigger value="saved" className="flex items-center gap-2">
                <Bookmark className="h-4 w-4" />
                Saved
              </TabsTrigger>
              <TabsTrigger value="history" className="flex items-center gap-2">
                <History className="h-4 w-4" />
                History
              </TabsTrigger>
              <TabsTrigger value="results" className="flex items-center gap-2">
                Results
                {searchResults?.total_count && (
                  <span className="ml-1 bg-blue-100 text-blue-800 text-xs font-medium px-2 py-0.5 rounded-full">
                    {searchResults.total_count}
                  </span>
                )}
              </TabsTrigger>
            </TabsList>

            <TabsContent value="search" className="mt-6">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Search className="h-5 w-5" />
                    Search Criteria
                    {selectedSavedSearch && (
                      <span className="ml-2 text-sm font-normal text-gray-500">
                        (Using: {selectedSavedSearch.search_name})
                      </span>
                    )}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <AdvancedSearchForm
                    criteria={searchCriteria}
                    onCriteriaChange={updateCriteria}
                    onSearch={executeSearch}
                    onReset={resetCriteria}
                    isLoading={isLoading}
                    error={error}
                  />
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="saved" className="mt-6">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Bookmark className="h-5 w-5" />
                    Saved Searches
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <SavedSearches
                    onSearchSelect={handleSavedSearchSelect}
                    currentCriteria={searchCriteria}
                  />
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="history" className="mt-6">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <History className="h-5 w-5" />
                    Search History
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <SearchHistory
                    onHistoryItemSelect={handleHistoryItemSelect}
                  />
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="results" className="mt-6">
              <SearchResults
                results={searchResults}
                isLoading={isLoading}
                error={error}
                onProspectView={(prospectId: number) => {
                  // Track prospect view for analytics
                  // This will be handled by the SearchResults component
                }}
              />
            </TabsContent>
          </Tabs>
        </div>

        {/* Sidebar */}
        <div className="lg:col-span-1">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Eye className="h-5 w-5" />
                Recently Viewed
              </CardTitle>
            </CardHeader>
            <CardContent>
              <RecentlyViewedProspects />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
