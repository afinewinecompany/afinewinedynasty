'use client';

import { useState } from 'react';
import { Slider } from './slider';

interface FilterState {
  position: string[];
  organization: string[];
  level: string[];
  etaMin?: number;
  etaMax?: number;
  ageMin?: number;
  ageMax?: number;
}

interface FilterPanelProps {
  filters: FilterState;
  onChange: (newFilters: Partial<FilterState>) => void;
  onClear: () => void;
  mobile?: boolean;
}

const POSITIONS = [
  { value: 'C', label: 'C' },
  { value: '1B', label: '1B' },
  { value: '2B', label: '2B' },
  { value: '3B', label: '3B' },
  { value: 'SS', label: 'SS' },
  { value: 'OF', label: 'OF' },
  { value: 'SP', label: 'SP' },
  { value: 'RP', label: 'RP' },
];

const ORGANIZATIONS = [
  'Arizona Diamondbacks',
  'Atlanta Braves',
  'Baltimore Orioles',
  'Boston Red Sox',
  'Chicago Cubs',
  'Chicago White Sox',
  'Cincinnati Reds',
  'Cleveland Guardians',
  'Colorado Rockies',
  'Detroit Tigers',
  'Houston Astros',
  'Kansas City Royals',
  'Los Angeles Angels',
  'Los Angeles Dodgers',
  'Miami Marlins',
  'Milwaukee Brewers',
  'Minnesota Twins',
  'New York Mets',
  'New York Yankees',
  'Oakland Athletics',
  'Philadelphia Phillies',
  'Pittsburgh Pirates',
  'San Diego Padres',
  'San Francisco Giants',
  'Seattle Mariners',
  'St. Louis Cardinals',
  'Tampa Bay Rays',
  'Texas Rangers',
  'Toronto Blue Jays',
  'Washington Nationals',
];

const LEVELS = [
  { value: 'MLB', label: 'MLB' },
  { value: 'AAA', label: 'AAA' },
  { value: 'AA', label: 'AA' },
  { value: 'A+', label: 'A+' },
  { value: 'A', label: 'A' },
  { value: 'Rookie', label: 'Rookie' },
];

const ETA_YEARS = [2024, 2025, 2026, 2027, 2028];

export default function FilterPanel({
  filters,
  onChange,
  onClear,
  mobile = false,
}: FilterPanelProps) {
  const [ageRange, setAgeRange] = useState<[number, number]>([
    filters.ageMin ?? 17,
    filters.ageMax ?? 24,
  ]);

  const togglePosition = (position: string) => {
    const newPositions = filters.position.includes(position)
      ? filters.position.filter((p) => p !== position)
      : [...filters.position, position];
    onChange({ position: newPositions });
  };

  const toggleLevel = (level: string) => {
    const newLevels = filters.level.includes(level)
      ? filters.level.filter((l) => l !== level)
      : [...filters.level, level];
    onChange({ level: newLevels });
  };

  const handleAgeChange = (value: number[]) => {
    setAgeRange([value[0], value[1]]);
    onChange({ ageMin: value[0], ageMax: value[1] });
  };

  const hasActiveFilters =
    filters.position.length > 0 ||
    filters.organization.length > 0 ||
    filters.level.length > 0 ||
    filters.etaMin !== undefined ||
    filters.etaMax !== undefined ||
    filters.ageMin !== undefined ||
    filters.ageMax !== undefined;

  return (
    <div className={`rounded-lg border border-gray-200 bg-white p-4 ${mobile ? 'w-full' : ''}`}>
      <h3 className="mb-4 text-lg font-semibold text-gray-900">Filters</h3>

      {/* Position Filters */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-3">
          Position
        </label>
        <div className="space-y-2">
          <label className="flex items-center">
            <input
              type="checkbox"
              checked={filters.position.length === 0}
              onChange={() => onChange({ position: [] })}
              className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span className="ml-2 text-sm text-gray-700">All Positions</span>
          </label>
          {POSITIONS.map((pos) => (
            <label key={pos.value} className="flex items-center">
              <input
                type="checkbox"
                checked={filters.position.includes(pos.value)}
                onChange={() => togglePosition(pos.value)}
                className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <span className="ml-2 text-sm text-gray-700">{pos.label}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Organization Filter */}
      <div className="mb-6">
        <label
          htmlFor="organization-select"
          className="block text-sm font-medium text-gray-700 mb-2"
        >
          Organization
        </label>
        <select
          id="organization-select"
          value={filters.organization[0] || ''}
          onChange={(e) =>
            onChange({
              organization: e.target.value ? [e.target.value] : [],
            })
          }
          className="block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          <option value="">All Teams</option>
          {ORGANIZATIONS.map((org) => (
            <option key={org} value={org}>
              {org}
            </option>
          ))}
        </select>
      </div>

      {/* Level Filter */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-3">
          Level
        </label>
        <div className="space-y-2">
          {LEVELS.map((level) => (
            <label key={level.value} className="flex items-center">
              <input
                type="checkbox"
                checked={filters.level.includes(level.value)}
                onChange={() => toggleLevel(level.value)}
                className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <span className="ml-2 text-sm text-gray-700">{level.label}</span>
            </label>
          ))}
        </div>
      </div>

      {/* ETA Filter */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-3">
          ETA
        </label>
        <div className="space-y-2">
          {ETA_YEARS.map((year) => {
            const count = Math.floor(Math.random() * 100); // Placeholder - should come from data
            const percentage = (count / 100) * 100;
            return (
              <div key={year} className="flex items-center justify-between">
                <label className="flex items-center flex-1">
                  <input
                    type="checkbox"
                    checked={
                      filters.etaMin === year || filters.etaMax === year
                    }
                    onChange={(e) => {
                      if (e.target.checked) {
                        onChange({ etaMin: year, etaMax: year });
                      } else {
                        onChange({ etaMin: undefined, etaMax: undefined });
                      }
                    }}
                    className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="ml-2 text-sm text-gray-700">{year}</span>
                </label>
                <div className="ml-4 flex-1">
                  <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-blue-500"
                      style={{ width: `${percentage}%` }}
                    />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Age Range Slider */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-3">
          Age Range
        </label>
        <div className="px-2">
          <div className="flex justify-between text-xs text-gray-600 mb-2">
            <span>{ageRange[0]}</span>
            <span>{ageRange[1]}</span>
          </div>
          <Slider
            value={ageRange}
            onValueChange={handleAgeChange}
            min={17}
            max={30}
            step={1}
            className="w-full"
          />
          <div className="flex justify-between text-xs text-gray-500 mt-1">
            <span>17</span>
            <span>30</span>
          </div>
        </div>
      </div>

      {/* Clear Filters Button */}
      {hasActiveFilters && (
        <button
          onClick={onClear}
          className="w-full rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
        >
          Clear Filters
        </button>
      )}
    </div>
  );
}
