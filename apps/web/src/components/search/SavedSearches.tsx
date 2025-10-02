'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api/client';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { AdvancedSearchCriteria } from '@/hooks/useAdvancedSearch';
import {
  Bookmark,
  Plus,
  Edit2,
  Trash2,
  Play,
  Calendar,
  Filter,
  Search
} from 'lucide-react';

/**
 * Represents a saved search with its metadata
 *
 * @interface SavedSearch
 * @since 1.0.0
 */
interface SavedSearch {
  /** Unique identifier for the saved search */
  id: number;
  /** User-defined name for the saved search */
  search_name: string;
  /** Serialized search criteria configuration */
  search_criteria: AdvancedSearchCriteria;
  /** ISO timestamp when the search was created */
  created_at: string;
  /** ISO timestamp when the search was last used */
  last_used: string;
}

/**
 * Props for the SavedSearches component
 *
 * @interface SavedSearchesProps
 * @since 1.0.0
 */
interface SavedSearchesProps {
  /** Callback triggered when a saved search is selected for execution */
  onSearchSelect: (savedSearch: SavedSearch) => void;
  /** Current search criteria to save as new search */
  currentCriteria: AdvancedSearchCriteria;
}

/**
 * Saved Searches Management Component
 *
 * Provides a complete interface for managing saved search criteria with full
 * CRUD (Create, Read, Update, Delete) operations. Integrates with the backend
 * saved search API and provides real-time updates using React Query.
 *
 * Features:
 * - Create new saved searches from current criteria
 * - Edit existing saved search names and criteria
 * - Delete saved searches with confirmation dialog
 * - Quick execution of saved searches with one click
 * - Visual indicators for active filters count
 * - Last used timestamps for organization
 * - Filter preview badges for quick identification
 * - Real-time synchronization with backend
 *
 * @component
 * @param {SavedSearchesProps} props - Component properties
 * @returns {JSX.Element} Saved searches management interface with CRUD operations
 *
 * @example
 * ```tsx
 * <SavedSearches
 *   onSearchSelect={(savedSearch) => {
 *     setCriteria(savedSearch.search_criteria);
 *     performSearch();
 *   }}
 *   currentCriteria={currentSearchCriteria}
 * />
 * ```
 *
 * @since 1.0.0
 * @version 3.4.0
 */
export function SavedSearches({ onSearchSelect, currentCriteria }: SavedSearchesProps) {
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [editingSearch, setEditingSearch] = useState<SavedSearch | null>(null);
  const [newSearchName, setNewSearchName] = useState('');
  const queryClient = useQueryClient();

  // Fetch saved searches
  const { data: savedSearches, isLoading } = useQuery({
    queryKey: ['saved-searches'],
    queryFn: async () => {
      const response = await api.get('/search/saved');
      return response.data as SavedSearch[];
    }
  });

  // Create saved search mutation
  const createMutation = useMutation({
    mutationFn: async (data: { search_name: string; search_criteria: any }) => {
      const response = await api.post('/search/saved', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['saved-searches'] });
      setIsCreateDialogOpen(false);
      setNewSearchName('');
    }
  });

  // Update saved search mutation
  const updateMutation = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: any }) => {
      const response = await api.put(`/search/saved/${id}`, data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['saved-searches'] });
      setEditingSearch(null);
    }
  });

  // Delete saved search mutation
  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/search/saved/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['saved-searches'] });
    }
  });

  const handleCreateSavedSearch = () => {
    if (!newSearchName.trim()) return;

    createMutation.mutate({
      search_name: newSearchName.trim(),
      search_criteria: currentCriteria
    });
  };

  const handleUpdateSavedSearch = () => {
    if (!editingSearch || !newSearchName.trim()) return;

    updateMutation.mutate({
      id: editingSearch.id,
      data: {
        search_name: newSearchName.trim(),
        search_criteria: editingSearch.search_criteria
      }
    });
  };

  const handleDeleteSavedSearch = (id: number) => {
    deleteMutation.mutate(id);
  };

  const getActiveFiltersCount = (criteria: AdvancedSearchCriteria) => {
    const { page, size, sort_by, ...filters } = criteria;
    return Object.values(filters).filter(value => {
      if (Array.isArray(value)) return value.length > 0;
      return value !== undefined && value !== null && value !== '';
    }).length;
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
  };

  const hasCurrentCriteria = getActiveFiltersCount(currentCriteria) > 0;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Create New Saved Search */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium">Your Saved Searches</h3>
        <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
          <DialogTrigger asChild>
            <Button
              variant="outline"
              size="sm"
              disabled={!hasCurrentCriteria}
              className="flex items-center gap-2"
            >
              <Plus className="h-4 w-4" />
              Save Current Search
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Save Search</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div>
                <Label htmlFor="search-name">Search Name</Label>
                <Input
                  id="search-name"
                  value={newSearchName}
                  onChange={(e) => setNewSearchName(e.target.value)}
                  placeholder="Enter a name for this search..."
                  className="mt-1"
                />
              </div>
              <div className="bg-gray-50 p-3 rounded-md">
                <p className="text-sm text-gray-600 mb-2">Current criteria will be saved:</p>
                <Badge variant="secondary">
                  {getActiveFiltersCount(currentCriteria)} active filter
                  {getActiveFiltersCount(currentCriteria) !== 1 ? 's' : ''}
                </Badge>
              </div>
              <div className="flex justify-end gap-2">
                <Button
                  variant="outline"
                  onClick={() => setIsCreateDialogOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleCreateSavedSearch}
                  disabled={!newSearchName.trim() || createMutation.isPending}
                >
                  {createMutation.isPending ? 'Saving...' : 'Save Search'}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {!hasCurrentCriteria && (
        <div className="text-center py-4 text-gray-500 text-sm">
          Set up search criteria to save a search
        </div>
      )}

      {/* Saved Searches List */}
      {savedSearches && savedSearches.length > 0 ? (
        <div className="space-y-3">
          {savedSearches.map((savedSearch) => (
            <Card key={savedSearch.id} className="hover:shadow-md transition-shadow">
              <CardContent className="p-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <Bookmark className="h-4 w-4 text-blue-500" />
                      <h4 className="font-medium">{savedSearch.search_name}</h4>
                      <Badge variant="outline" className="text-xs">
                        {getActiveFiltersCount(savedSearch.search_criteria)} filter
                        {getActiveFiltersCount(savedSearch.search_criteria) !== 1 ? 's' : ''}
                      </Badge>
                    </div>

                    <div className="flex items-center gap-4 text-xs text-gray-500 mb-3">
                      <span className="flex items-center gap-1">
                        <Calendar className="h-3 w-3" />
                        Created: {formatDate(savedSearch.created_at)}
                      </span>
                      <span className="flex items-center gap-1">
                        Last used: {formatDate(savedSearch.last_used)}
                      </span>
                    </div>

                    {/* Filter Preview */}
                    <div className="flex flex-wrap gap-1 mb-3">
                      {savedSearch.search_criteria.search_query && (
                        <Badge variant="secondary" className="text-xs">
                          <Search className="h-3 w-3 mr-1" />
                          "{savedSearch.search_criteria.search_query}"
                        </Badge>
                      )}
                      {savedSearch.search_criteria.positions && savedSearch.search_criteria.positions.length > 0 && (
                        <Badge variant="secondary" className="text-xs">
                          Positions: {savedSearch.search_criteria.positions.slice(0, 2).join(', ')}
                          {savedSearch.search_criteria.positions.length > 2 && ' +more'}
                        </Badge>
                      )}
                      {savedSearch.search_criteria.min_batting_avg && (
                        <Badge variant="secondary" className="text-xs">
                          BA ≥ {savedSearch.search_criteria.min_batting_avg}
                        </Badge>
                      )}
                      {savedSearch.search_criteria.min_overall_grade && (
                        <Badge variant="secondary" className="text-xs">
                          Grade ≥ {savedSearch.search_criteria.min_overall_grade}
                        </Badge>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2 ml-4">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onSearchSelect(savedSearch)}
                      className="flex items-center gap-1"
                    >
                      <Play className="h-3 w-3" />
                      Run
                    </Button>

                    <Dialog
                      open={editingSearch?.id === savedSearch.id}
                      onOpenChange={(open) => {
                        if (open) {
                          setEditingSearch(savedSearch);
                          setNewSearchName(savedSearch.search_name);
                        } else {
                          setEditingSearch(null);
                          setNewSearchName('');
                        }
                      }}
                    >
                      <DialogTrigger asChild>
                        <Button variant="ghost" size="sm">
                          <Edit2 className="h-3 w-3" />
                        </Button>
                      </DialogTrigger>
                      <DialogContent>
                        <DialogHeader>
                          <DialogTitle>Edit Saved Search</DialogTitle>
                        </DialogHeader>
                        <div className="space-y-4">
                          <div>
                            <Label htmlFor="edit-search-name">Search Name</Label>
                            <Input
                              id="edit-search-name"
                              value={newSearchName}
                              onChange={(e) => setNewSearchName(e.target.value)}
                              className="mt-1"
                            />
                          </div>
                          <div className="flex justify-end gap-2">
                            <Button
                              variant="outline"
                              onClick={() => setEditingSearch(null)}
                            >
                              Cancel
                            </Button>
                            <Button
                              onClick={handleUpdateSavedSearch}
                              disabled={!newSearchName.trim() || updateMutation.isPending}
                            >
                              {updateMutation.isPending ? 'Updating...' : 'Update'}
                            </Button>
                          </div>
                        </div>
                      </DialogContent>
                    </Dialog>

                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button variant="ghost" size="sm" className="text-red-600 hover:text-red-700">
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>Delete Saved Search</AlertDialogTitle>
                          <AlertDialogDescription>
                            Are you sure you want to delete "{savedSearch.search_name}"?
                            This action cannot be undone.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Cancel</AlertDialogCancel>
                          <AlertDialogAction
                            onClick={() => handleDeleteSavedSearch(savedSearch.id)}
                            className="bg-red-600 hover:bg-red-700"
                          >
                            Delete
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <div className="text-center py-8">
          <Bookmark className="h-12 w-12 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No saved searches yet</h3>
          <p className="text-gray-500 mb-4">
            Create search criteria and save them for quick access later
          </p>
        </div>
      )}

      {/* Error Messages */}
      {createMutation.error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-3">
          <p className="text-red-800 text-sm">
            Failed to save search: {(createMutation.error as any).message}
          </p>
        </div>
      )}

      {deleteMutation.error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-3">
          <p className="text-red-800 text-sm">
            Failed to delete search: {(deleteMutation.error as any).message}
          </p>
        </div>
      )}
    </div>
  );
}