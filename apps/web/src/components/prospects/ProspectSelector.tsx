'use client';

import { useState, useEffect, useCallback } from 'react';
import { Search, X, Filter } from 'lucide-react';
import { debounce } from 'lodash';

interface Prospect {
  id: number;
  name: string;
  position: string;
  organization: string;
  level: string;
  age: number;
  eta_year: number;
  dynasty_score: number;
  dynasty_rank: number;
}

interface ProspectSelectorProps {
  onSelect: (prospect: Prospect) => void;
  onClose: () => void;
  excludeIds?: number[];
}

const POSITIONS = ['C', '1B', '2B', '3B', 'SS', 'OF', 'SP', 'RP'];
const LEVELS = ['Rookie', 'A', 'A+', 'AA', 'AAA'];

export default function ProspectSelector({
  onSelect,
  onClose,
  excludeIds = [],
}: ProspectSelectorProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [prospects, setProspects] = useState<Prospect[]>([]);
  const [filteredProspects, setFilteredProspects] = useState<Prospect[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [selectedPositions, setSelectedPositions] = useState<string[]>([]);
  const [selectedLevels, setSelectedLevels] = useState<string[]>([]);
  const [ageRange, setAgeRange] = useState<{ min: number; max: number }>({
    min: 16,
    max: 30,
  });
  const [showFilters, setShowFilters] = useState(false);

  // Autocomplete suggestions
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);

  // Fetch prospects data
  const fetchProspects = useCallback(
    async (query = '', filters = {}) => {
      setIsLoading(true);
      setError(null);

      try {
        const params = new URLSearchParams();

        if (query) params.append('search', query);
        if (filters.positions?.length) {
          filters.positions.forEach((pos) => params.append('position', pos));
        }
        if (filters.levels?.length) {
          filters.levels.forEach((level) => params.append('level', level));
        }
        if (filters.ageMin) params.append('age_min', filters.ageMin.toString());
        if (filters.ageMax) params.append('age_max', filters.ageMax.toString());

        params.append('page_size', '50');
        params.append('sort_by', 'dynasty_rank');

        const response = await fetch(`/api/prospects/?${params.toString()}`, {
          headers: {
            Authorization: `Bearer ${localStorage.getItem('token')}`,
          },
        });

        if (!response.ok) {
          throw new Error('Failed to fetch prospects');
        }

        const data = await response.json();
        const prospectsData = data.prospects || [];

        // Filter out excluded prospects
        const filtered = prospectsData.filter(
          (p) => !excludeIds.includes(p.id)
        );

        setProspects(filtered);
        setFilteredProspects(filtered);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setIsLoading(false);
      }
    },
    [excludeIds]
  );

  // Debounced search
  const debouncedSearch = useCallback(
    debounce((query: string) => {
      const filters = {
        positions: selectedPositions,
        levels: selectedLevels,
        ageMin: ageRange.min,
        ageMax: ageRange.max,
      };
      fetchProspects(query, filters);
    }, 300),
    [selectedPositions, selectedLevels, ageRange, fetchProspects]
  );

  // Fetch autocomplete suggestions
  const fetchSuggestions = useCallback(
    debounce(async (query: string) => {
      if (query.length < 2) {
        setSuggestions([]);
        return;
      }

      try {
        const response = await fetch(
          `/api/prospects/search/autocomplete?q=${encodeURIComponent(query)}`,
          {
            headers: {
              Authorization: `Bearer ${localStorage.getItem('token')}`,
            },
          }
        );

        if (response.ok) {
          const data = await response.json();
          setSuggestions(data.map((item) => item.display));
        }
      } catch (err) {
        console.error('Failed to fetch suggestions:', err);
      }
    }, 200),
    []
  );

  // Handle search input change
  const handleSearchChange = (value: string) => {
    setSearchQuery(value);
    setShowSuggestions(value.length >= 2);

    if (value.length >= 2) {
      fetchSuggestions(value);
      debouncedSearch(value);
    } else if (value.length === 0) {
      // Reset to initial state when search is cleared
      const filters = {
        positions: selectedPositions,
        levels: selectedLevels,
        ageMin: ageRange.min,
        ageMax: ageRange.max,
      };
      fetchProspects('', filters);
    }
  };

  // Handle filter changes
  const handleFilterChange = () => {
    const filters = {
      positions: selectedPositions,
      levels: selectedLevels,
      ageMin: ageRange.min,
      ageMax: ageRange.max,
    };
    fetchProspects(searchQuery, filters);
  };

  // Position filter toggle
  const togglePosition = (position: string) => {
    setSelectedPositions((prev) =>
      prev.includes(position)
        ? prev.filter((p) => p !== position)
        : [...prev, position]
    );
  };

  // Level filter toggle
  const toggleLevel = (level: string) => {
    setSelectedLevels((prev) =>
      prev.includes(level) ? prev.filter((l) => l !== level) : [...prev, level]
    );
  };

  // Initial load
  useEffect(() => {
    fetchProspects();
  }, [fetchProspects]);

  // Apply filters when they change
  useEffect(() => {
    if (prospects.length > 0) {
      handleFilterChange();
    }
  }, [selectedPositions, selectedLevels, ageRange]);

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b">
          <h2 className="text-xl font-semibold text-gray-900">
            Select Prospect to Compare
          </h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Search and Filters */}
        <div className="p-6 border-b space-y-4">
          {/* Search Bar */}
          <div className="relative">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
              <input
                type="text"
                placeholder="Search prospects by name or organization..."
                value={searchQuery}
                onChange={(e) => handleSearchChange(e.target.value)}
                className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            {/* Autocomplete Suggestions */}
            {showSuggestions && suggestions.length > 0 && (
              <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-300 rounded-lg shadow-lg z-10 max-h-40 overflow-y-auto">
                {suggestions.map((suggestion, index) => (
                  <button
                    key={index}
                    onClick={() => {
                      setSearchQuery(suggestion);
                      setShowSuggestions(false);
                      debouncedSearch(suggestion);
                    }}
                    className="w-full text-left px-4 py-2 hover:bg-gray-50 text-sm"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Filter Toggle */}
          <div className="flex items-center justify-between">
            <button
              onClick={() => setShowFilters(!showFilters)}
              className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md transition-colors"
            >
              <Filter className="w-4 h-4" />
              Filters
              {(selectedPositions.length > 0 || selectedLevels.length > 0) && (
                <span className="ml-1 px-2 py-1 text-xs bg-blue-100 text-blue-800 rounded-full">
                  {selectedPositions.length + selectedLevels.length}
                </span>
              )}
            </button>

            <div className="text-sm text-gray-500">
              {filteredProspects.length} prospects found
            </div>
          </div>

          {/* Filters Panel */}
          {showFilters && (
            <div className="bg-gray-50 rounded-lg p-4 space-y-4">
              {/* Position Filters */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Position
                </label>
                <div className="flex flex-wrap gap-2">
                  {POSITIONS.map((position) => (
                    <button
                      key={position}
                      onClick={() => togglePosition(position)}
                      className={`px-3 py-1 text-sm rounded-full border transition-colors ${
                        selectedPositions.includes(position)
                          ? 'bg-blue-100 border-blue-300 text-blue-800'
                          : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50'
                      }`}
                    >
                      {position}
                    </button>
                  ))}
                </div>
              </div>

              {/* Level Filters */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Level
                </label>
                <div className="flex flex-wrap gap-2">
                  {LEVELS.map((level) => (
                    <button
                      key={level}
                      onClick={() => toggleLevel(level)}
                      className={`px-3 py-1 text-sm rounded-full border transition-colors ${
                        selectedLevels.includes(level)
                          ? 'bg-green-100 border-green-300 text-green-800'
                          : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50'
                      }`}
                    >
                      {level}
                    </button>
                  ))}
                </div>
              </div>

              {/* Age Range */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Age Range: {ageRange.min} - {ageRange.max}
                </label>
                <div className="flex items-center gap-4">
                  <input
                    type="range"
                    min="16"
                    max="30"
                    value={ageRange.min}
                    onChange={(e) =>
                      setAgeRange((prev) => ({
                        ...prev,
                        min: parseInt(e.target.value),
                      }))
                    }
                    className="flex-1"
                  />
                  <input
                    type="range"
                    min="16"
                    max="30"
                    value={ageRange.max}
                    onChange={(e) =>
                      setAgeRange((prev) => ({
                        ...prev,
                        max: parseInt(e.target.value),
                      }))
                    }
                    className="flex-1"
                  />
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Results */}
        <div className="p-6 max-h-96 overflow-y-auto">
          {isLoading ? (
            <div className="text-center py-8">
              <div className="animate-spin w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full mx-auto mb-4"></div>
              <p className="text-gray-600">Searching prospects...</p>
            </div>
          ) : error ? (
            <div className="text-center py-8">
              <p className="text-red-600 font-medium">
                Error loading prospects
              </p>
              <p className="text-sm text-gray-500 mt-1">{error}</p>
            </div>
          ) : filteredProspects.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-gray-600">
                No prospects found matching your criteria
              </p>
              <button
                onClick={() => {
                  setSearchQuery('');
                  setSelectedPositions([]);
                  setSelectedLevels([]);
                  setAgeRange({ min: 16, max: 30 });
                  fetchProspects();
                }}
                className="mt-2 text-blue-600 hover:text-blue-700 text-sm font-medium"
              >
                Clear all filters
              </button>
            </div>
          ) : (
            <div className="grid gap-3">
              {filteredProspects.map((prospect) => (
                <button
                  key={prospect.id}
                  onClick={() => onSelect(prospect)}
                  className="p-4 border border-gray-200 rounded-lg hover:border-blue-300 hover:bg-blue-50 transition-colors text-left"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-medium text-gray-900">
                        {prospect.name}
                      </h3>
                      <div className="text-sm text-gray-600 mt-1">
                        {prospect.position} • {prospect.organization} •{' '}
                        {prospect.level}
                      </div>
                      <div className="text-sm text-gray-500">
                        Age {prospect.age} • ETA {prospect.eta_year || 'TBD'}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-medium text-gray-900">
                        #{prospect.dynasty_rank}
                      </div>
                      <div className="text-xs text-gray-500">
                        Score: {prospect.dynasty_score?.toFixed(1)}
                      </div>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
