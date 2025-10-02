'use client';

import { useState } from 'react';

interface FilterPanelProps {
  selectedPosition: string;
  selectedOrganization: string;
  onPositionChange: (position: string) => void;
  onOrganizationChange: (organization: string) => void;
  onClearFilters: () => void;
  className?: string;
  isMobile?: boolean;
}

const POSITIONS = [
  { value: '', label: 'All Positions' },
  { value: 'C', label: 'Catcher' },
  { value: '1B', label: 'First Base' },
  { value: '2B', label: 'Second Base' },
  { value: '3B', label: 'Third Base' },
  { value: 'SS', label: 'Shortstop' },
  { value: 'OF', label: 'Outfield' },
  { value: 'DH', label: 'Designated Hitter' },
  { value: 'RHP', label: 'Right-Handed Pitcher' },
  { value: 'LHP', label: 'Left-Handed Pitcher' },
];

const ORGANIZATIONS = [
  { value: '', label: 'All Organizations' },
  { value: 'Arizona Diamondbacks', label: 'Arizona Diamondbacks' },
  { value: 'Atlanta Braves', label: 'Atlanta Braves' },
  { value: 'Baltimore Orioles', label: 'Baltimore Orioles' },
  { value: 'Boston Red Sox', label: 'Boston Red Sox' },
  { value: 'Chicago Cubs', label: 'Chicago Cubs' },
  { value: 'Chicago White Sox', label: 'Chicago White Sox' },
  { value: 'Cincinnati Reds', label: 'Cincinnati Reds' },
  { value: 'Cleveland Guardians', label: 'Cleveland Guardians' },
  { value: 'Colorado Rockies', label: 'Colorado Rockies' },
  { value: 'Detroit Tigers', label: 'Detroit Tigers' },
  { value: 'Houston Astros', label: 'Houston Astros' },
  { value: 'Kansas City Royals', label: 'Kansas City Royals' },
  { value: 'Los Angeles Angels', label: 'Los Angeles Angels' },
  { value: 'Los Angeles Dodgers', label: 'Los Angeles Dodgers' },
  { value: 'Miami Marlins', label: 'Miami Marlins' },
  { value: 'Milwaukee Brewers', label: 'Milwaukee Brewers' },
  { value: 'Minnesota Twins', label: 'Minnesota Twins' },
  { value: 'New York Mets', label: 'New York Mets' },
  { value: 'New York Yankees', label: 'New York Yankees' },
  { value: 'Oakland Athletics', label: 'Oakland Athletics' },
  { value: 'Philadelphia Phillies', label: 'Philadelphia Phillies' },
  { value: 'Pittsburgh Pirates', label: 'Pittsburgh Pirates' },
  { value: 'San Diego Padres', label: 'San Diego Padres' },
  { value: 'San Francisco Giants', label: 'San Francisco Giants' },
  { value: 'Seattle Mariners', label: 'Seattle Mariners' },
  { value: 'St. Louis Cardinals', label: 'St. Louis Cardinals' },
  { value: 'Tampa Bay Rays', label: 'Tampa Bay Rays' },
  { value: 'Texas Rangers', label: 'Texas Rangers' },
  { value: 'Toronto Blue Jays', label: 'Toronto Blue Jays' },
  { value: 'Washington Nationals', label: 'Washington Nationals' },
];

export default function FilterPanel({
  selectedPosition,
  selectedOrganization,
  onPositionChange,
  onOrganizationChange,
  onClearFilters,
  className = '',
  isMobile = false,
}: FilterPanelProps) {
  const [isOpen, setIsOpen] = useState(false);

  const hasFilters = selectedPosition || selectedOrganization;

  if (isMobile) {
    return (
      <>
        <button
          onClick={() => setIsOpen(true)}
          className="flex items-center justify-center rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          <svg className="mr-2 h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
            <path
              fillRule="evenodd"
              d="M2.628 1.601C5.028 1.206 7.49 1 10 1s4.973.206 7.372.601a.75.75 0 01.628.74v2.288a2.25 2.25 0 01-.659 1.59l-4.682 4.683a2.25 2.25 0 00-.659 1.59v3.037c0 .684-.31 1.33-.844 1.757l-1.937 1.55A.75.75 0 018 18.25v-5.757a2.25 2.25 0 00-.659-1.591L2.659 6.22A2.25 2.25 0 012 4.629V2.34a.75.75 0 01.628-.74z"
              clipRule="evenodd"
            />
          </svg>
          Filters{' '}
          {hasFilters && (
            <span className="ml-1 rounded-full bg-blue-100 px-2 py-0.5 text-xs text-blue-800">
              Active
            </span>
          )}
        </button>

        {isOpen && (
          <div className="fixed inset-0 z-50 overflow-y-auto">
            <div className="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
              <div
                className="fixed inset-0 bg-gray-500 bg-opacity-75"
                onClick={() => setIsOpen(false)}
              />
              <div className="relative w-full max-w-md transform overflow-hidden rounded-lg bg-white px-4 pb-4 pt-5 text-left shadow-xl transition-all">
                <div className="flex items-center justify-between pb-4">
                  <h3 className="text-lg font-medium text-gray-900">Filters</h3>
                  <button
                    onClick={() => setIsOpen(false)}
                    className="rounded-md bg-white text-gray-400 hover:text-gray-500"
                  >
                    <svg
                      className="h-6 w-6"
                      fill="none"
                      viewBox="0 0 24 24"
                      strokeWidth="1.5"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M6 18L18 6M6 6l12 12"
                      />
                    </svg>
                  </button>
                </div>
                <div className="space-y-4">
                  <div>
                    <label
                      htmlFor="position-select"
                      className="block text-sm font-medium text-gray-700 mb-2"
                    >
                      Position
                    </label>
                    <select
                      id="position-select"
                      value={selectedPosition}
                      onChange={(e) => onPositionChange(e.target.value)}
                      className="block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    >
                      {POSITIONS.map((position) => (
                        <option key={position.value} value={position.value}>
                          {position.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label
                      htmlFor="organization-select"
                      className="block text-sm font-medium text-gray-700 mb-2"
                    >
                      Organization
                    </label>
                    <select
                      id="organization-select"
                      value={selectedOrganization}
                      onChange={(e) => onOrganizationChange(e.target.value)}
                      className="block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    >
                      {ORGANIZATIONS.map((org) => (
                        <option key={org.value} value={org.value}>
                          {org.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  {hasFilters && (
                    <button
                      onClick={() => {
                        onClearFilters();
                        setIsOpen(false);
                      }}
                      className="w-full rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
                    >
                      Clear Filters
                    </button>
                  )}
                </div>
                <div className="mt-6">
                  <button
                    onClick={() => setIsOpen(false)}
                    className="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
                  >
                    Apply Filters
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </>
    );
  }

  return (
    <div
      className={`rounded-lg border border-gray-200 bg-white p-4 ${className}`}
    >
      <h3 className="mb-4 text-lg font-medium text-gray-900">Filters</h3>
      <div className="space-y-4">
        <div>
          <label
            htmlFor="desktop-position-select"
            className="block text-sm font-medium text-gray-700 mb-2"
          >
            Position
          </label>
          <select
            id="desktop-position-select"
            value={selectedPosition}
            onChange={(e) => onPositionChange(e.target.value)}
            className="block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            {POSITIONS.map((position) => (
              <option key={position.value} value={position.value}>
                {position.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label
            htmlFor="desktop-organization-select"
            className="block text-sm font-medium text-gray-700 mb-2"
          >
            Organization
          </label>
          <select
            id="desktop-organization-select"
            value={selectedOrganization}
            onChange={(e) => onOrganizationChange(e.target.value)}
            className="block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            {ORGANIZATIONS.map((org) => (
              <option key={org.value} value={org.value}>
                {org.label}
              </option>
            ))}
          </select>
        </div>
        {hasFilters && (
          <button
            onClick={onClearFilters}
            className="w-full rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Clear Filters
          </button>
        )}
      </div>
    </div>
  );
}
