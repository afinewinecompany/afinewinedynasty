'use client';

interface ProspectsFilterPanelProps {
  selectedPosition: string;
  selectedOrganization: string;
  onPositionChange: (position: string) => void;
  onOrganizationChange: (organization: string) => void;
  onClearFilters: () => void;
  isMobile?: boolean;
}

const POSITIONS = ['C', '1B', '2B', '3B', 'SS', 'OF', 'SP', 'RP'];

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

export default function ProspectsFilterPanel({
  selectedPosition,
  selectedOrganization,
  onPositionChange,
  onOrganizationChange,
  onClearFilters,
  isMobile = false,
}: ProspectsFilterPanelProps) {
  const hasActiveFilters = selectedPosition || selectedOrganization;

  return (
    <div
      className={`rounded-lg border border-border bg-card p-4 ${isMobile ? 'w-full' : ''}`}
    >
      <h3 className="mb-4 text-lg font-semibold text-foreground">Filters</h3>

      {/* Position Filter */}
      <div className="mb-6">
        <label
          htmlFor="position-select"
          className="block text-sm font-medium text-foreground mb-2"
        >
          Position
        </label>
        <select
          id="position-select"
          value={selectedPosition}
          onChange={(e) => onPositionChange(e.target.value)}
          className="block w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
        >
          <option value="">All Positions</option>
          {POSITIONS.map((pos) => (
            <option key={pos} value={pos}>
              {pos}
            </option>
          ))}
        </select>
      </div>

      {/* Organization Filter */}
      <div className="mb-6">
        <label
          htmlFor="organization-select"
          className="block text-sm font-medium text-foreground mb-2"
        >
          Organization
        </label>
        <select
          id="organization-select"
          value={selectedOrganization}
          onChange={(e) => onOrganizationChange(e.target.value)}
          className="block w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
        >
          <option value="">All Teams</option>
          {ORGANIZATIONS.map((org) => (
            <option key={org} value={org}>
              {org}
            </option>
          ))}
        </select>
      </div>

      {/* Clear Filters Button */}
      {hasActiveFilters && (
        <button
          onClick={onClearFilters}
          className="w-full rounded-md border border-border bg-background px-4 py-2 text-sm font-medium text-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
        >
          Clear Filters
        </button>
      )}
    </div>
  );
}
