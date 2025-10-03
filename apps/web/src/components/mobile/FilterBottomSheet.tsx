/**
 * Mobile-optimized bottom sheet filter interface
 *
 * @component FilterBottomSheet
 * @since 1.0.0
 */

import React, { useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';

/**
 * Filter configuration interface
 *
 * @interface FilterConfig
 */
interface FilterConfig {
  position?: string;
  organization?: string;
  minAge?: number;
  maxAge?: number;
  eta?: string;
  minRank?: number;
  maxRank?: number;
}

/**
 * Props for FilterBottomSheet component
 *
 * @interface FilterBottomSheetProps
 */
interface FilterBottomSheetProps {
  /** Whether the sheet is open */
  isOpen: boolean;

  /** Callback to close the sheet */
  onClose: () => void;

  /** Current filter configuration */
  filters: FilterConfig;

  /** Callback when filters are applied */
  onApplyFilters: (filters: FilterConfig) => void;

  /** Number of active filters */
  activeFilterCount?: number;
}

/**
 * Bottom sheet filter interface for mobile with touch-optimized controls
 *
 * Slides up from bottom with smooth animations, collapsible sections
 * Touch-friendly controls with 44px minimum targets
 *
 * @param {FilterBottomSheetProps} props - Component props
 * @returns {JSX.Element} Rendered filter bottom sheet
 *
 * @example
 * ```tsx
 * <FilterBottomSheet
 *   isOpen={showFilters}
 *   onClose={() => setShowFilters(false)}
 *   filters={currentFilters}
 *   onApplyFilters={handleApplyFilters}
 * />
 * ```
 */
export const FilterBottomSheet: React.FC<FilterBottomSheetProps> = ({
  isOpen,
  onClose,
  filters,
  onApplyFilters,
  activeFilterCount = 0,
}) => {
  const [localFilters, setLocalFilters] = React.useState<FilterConfig>(filters);
  const sheetRef = useRef<HTMLDivElement>(null);

  // Update local filters when prop filters change
  useEffect(() => {
    setLocalFilters(filters);
  }, [filters]);

  // Handle backdrop click
  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  // Handle apply filters
  const handleApply = () => {
    onApplyFilters(localFilters);
    onClose();
  };

  // Handle clear filters
  const handleClear = () => {
    setLocalFilters({});
  };

  // Touch gesture handling for swipe down to close
  useEffect(() => {
    if (!isOpen || !sheetRef.current) return;

    let startY = 0;
    let currentY = 0;

    const handleTouchStart = (e: TouchEvent) => {
      startY = e.touches[0].clientY;
      currentY = startY;
    };

    const handleTouchMove = (e: TouchEvent) => {
      currentY = e.touches[0].clientY;
    };

    const handleTouchEnd = () => {
      const deltaY = currentY - startY;

      // If swiping down more than 100px, close the sheet
      if (deltaY > 100) {
        onClose();
      }
    };

    const sheet = sheetRef.current;
    sheet.addEventListener('touchstart', handleTouchStart, { passive: true });
    sheet.addEventListener('touchmove', handleTouchMove, { passive: true });
    sheet.addEventListener('touchend', handleTouchEnd);

    return () => {
      sheet.removeEventListener('touchstart', handleTouchStart);
      sheet.removeEventListener('touchmove', handleTouchMove);
      sheet.removeEventListener('touchend', handleTouchEnd);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const positions = ['C', '1B', '2B', '3B', 'SS', 'OF', 'DH', 'P'];
  const organizations = ['MLB', 'AAA', 'AA', 'A+', 'A', 'Rookie'];
  const etaOptions = ['2024', '2025', '2026', '2027', '2028+'];

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black bg-opacity-50 z-40 transition-opacity duration-300"
        onClick={handleBackdropClick}
        aria-hidden="true"
      />

      {/* Bottom Sheet */}
      <div
        ref={sheetRef}
        className={`
          fixed bottom-0 left-0 right-0 z-50
          transform transition-transform duration-300
          ${isOpen ? 'translate-y-0' : 'translate-y-full'}
          max-h-[80vh] overflow-y-auto
          bg-white rounded-t-2xl shadow-xl
        `}
        role="dialog"
        aria-modal="true"
        aria-label="Filter options"
      >
        {/* Drag handle */}
        <div className="flex justify-center py-2">
          <div className="w-12 h-1 bg-gray-300 rounded-full" />
        </div>

        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">Filters</CardTitle>
            {activeFilterCount > 0 && (
              <Badge variant="secondary">{activeFilterCount} active</Badge>
            )}
          </div>
        </CardHeader>

        <CardContent className="pb-20">
          {/* Quick Filter Chips */}
          <div className="mb-4">
            <Label className="text-sm font-medium mb-2 block">
              Quick Filters
            </Label>
            <div className="flex flex-wrap gap-2">
              <Button
                variant={localFilters.position === 'OF' ? 'default' : 'outline'}
                size="sm"
                className="min-h-[44px]"
                onClick={() =>
                  setLocalFilters({
                    ...localFilters,
                    position: localFilters.position === 'OF' ? undefined : 'OF',
                  })
                }
              >
                Outfielders
              </Button>
              <Button
                variant={localFilters.position === 'P' ? 'default' : 'outline'}
                size="sm"
                className="min-h-[44px]"
                onClick={() =>
                  setLocalFilters({
                    ...localFilters,
                    position: localFilters.position === 'P' ? undefined : 'P',
                  })
                }
              >
                Pitchers
              </Button>
              <Button
                variant={localFilters.maxRank === 25 ? 'default' : 'outline'}
                size="sm"
                className="min-h-[44px]"
                onClick={() =>
                  setLocalFilters({
                    ...localFilters,
                    maxRank: localFilters.maxRank === 25 ? undefined : 25,
                  })
                }
              >
                Top 25
              </Button>
              <Button
                variant={localFilters.eta === '2024' ? 'default' : 'outline'}
                size="sm"
                className="min-h-[44px]"
                onClick={() =>
                  setLocalFilters({
                    ...localFilters,
                    eta: localFilters.eta === '2024' ? undefined : '2024',
                  })
                }
              >
                MLB Ready
              </Button>
            </div>
          </div>

          {/* Position Filter */}
          <div className="mb-4">
            <Label
              htmlFor="position"
              className="text-sm font-medium mb-2 block"
            >
              Position
            </Label>
            <Select
              value={localFilters.position || ''}
              onValueChange={(value) =>
                setLocalFilters({
                  ...localFilters,
                  position: value || undefined,
                })
              }
            >
              <SelectTrigger id="position" className="min-h-[44px]">
                <SelectValue placeholder="All positions" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">All positions</SelectItem>
                {positions.map((pos) => (
                  <SelectItem key={pos} value={pos}>
                    {pos}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Organization Filter */}
          <div className="mb-4">
            <Label
              htmlFor="organization"
              className="text-sm font-medium mb-2 block"
            >
              Level
            </Label>
            <Select
              value={localFilters.organization || ''}
              onValueChange={(value) =>
                setLocalFilters({
                  ...localFilters,
                  organization: value || undefined,
                })
              }
            >
              <SelectTrigger id="organization" className="min-h-[44px]">
                <SelectValue placeholder="All levels" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">All levels</SelectItem>
                {organizations.map((org) => (
                  <SelectItem key={org} value={org}>
                    {org}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* ETA Filter */}
          <div className="mb-4">
            <Label htmlFor="eta" className="text-sm font-medium mb-2 block">
              ETA
            </Label>
            <Select
              value={localFilters.eta || ''}
              onValueChange={(value) =>
                setLocalFilters({ ...localFilters, eta: value || undefined })
              }
            >
              <SelectTrigger id="eta" className="min-h-[44px]">
                <SelectValue placeholder="Any ETA" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">Any ETA</SelectItem>
                {etaOptions.map((eta) => (
                  <SelectItem key={eta} value={eta}>
                    {eta}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Age Range Filter */}
          <div className="mb-4">
            <Label className="text-sm font-medium mb-2 block">Age Range</Label>
            <div className="flex gap-2 items-center">
              <input
                type="number"
                placeholder="Min"
                min="16"
                max="30"
                value={localFilters.minAge || ''}
                onChange={(e) =>
                  setLocalFilters({
                    ...localFilters,
                    minAge: e.target.value
                      ? parseInt(e.target.value)
                      : undefined,
                  })
                }
                className="flex-1 min-h-[44px] px-3 py-2 border border-gray-300 rounded-md"
              />
              <span className="text-gray-500">to</span>
              <input
                type="number"
                placeholder="Max"
                min="16"
                max="30"
                value={localFilters.maxAge || ''}
                onChange={(e) =>
                  setLocalFilters({
                    ...localFilters,
                    maxAge: e.target.value
                      ? parseInt(e.target.value)
                      : undefined,
                  })
                }
                className="flex-1 min-h-[44px] px-3 py-2 border border-gray-300 rounded-md"
              />
            </div>
          </div>

          {/* Rank Range Filter */}
          <div className="mb-6">
            <Label className="text-sm font-medium mb-2 block">Rank Range</Label>
            <div className="flex gap-2 items-center">
              <input
                type="number"
                placeholder="Min"
                min="1"
                max="500"
                value={localFilters.minRank || ''}
                onChange={(e) =>
                  setLocalFilters({
                    ...localFilters,
                    minRank: e.target.value
                      ? parseInt(e.target.value)
                      : undefined,
                  })
                }
                className="flex-1 min-h-[44px] px-3 py-2 border border-gray-300 rounded-md"
              />
              <span className="text-gray-500">to</span>
              <input
                type="number"
                placeholder="Max"
                min="1"
                max="500"
                value={localFilters.maxRank || ''}
                onChange={(e) =>
                  setLocalFilters({
                    ...localFilters,
                    maxRank: e.target.value
                      ? parseInt(e.target.value)
                      : undefined,
                  })
                }
                className="flex-1 min-h-[44px] px-3 py-2 border border-gray-300 rounded-md"
              />
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex gap-3">
            <Button
              variant="outline"
              className="flex-1 min-h-[44px]"
              onClick={handleClear}
            >
              Clear All
            </Button>
            <Button
              variant="default"
              className="flex-1 min-h-[44px]"
              onClick={handleApply}
            >
              Apply Filters
            </Button>
          </div>
        </CardContent>
      </div>
    </>
  );
};

export default FilterBottomSheet;
