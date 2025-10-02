'use client';

import { useState } from 'react';
import { AdvancedSearchCriteria } from '@/hooks/useAdvancedSearch';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Checkbox } from '@/components/ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import {
  Search,
  ChevronDown,
  ChevronRight,
  BarChart3,
  Target,
  Brain,
  Calendar,
  X,
  Filter
} from 'lucide-react';

/**
 * Props for the AdvancedSearchForm component
 *
 * @interface AdvancedSearchFormProps
 * @since 1.0.0
 */
interface AdvancedSearchFormProps {
  /** Current search criteria state */
  criteria: AdvancedSearchCriteria;
  /** Callback to update search criteria with partial updates */
  onCriteriaChange: (updates: Partial<AdvancedSearchCriteria>) => void;
  /** Callback triggered when search button is clicked */
  onSearch: () => void;
  /** Callback to reset all search criteria to defaults */
  onReset: () => void;
  /** Loading state indicator for search operation */
  isLoading: boolean;
  /** Error object from failed search operations */
  error: any;
}

/**
 * Advanced Search Form Component
 *
 * Provides dynamic criteria builders for complex prospect searches with
 * collapsible sections for different filter categories. Allows users to
 * build sophisticated queries combining statistical, scouting, ML prediction,
 * and timeline-based filters.
 *
 * Features:
 * - Statistical filters (batting avg, ERA, OBP, slugging, etc.)
 * - Scouting grade filters (20-80 scale with risk levels)
 * - ML prediction filters (confidence, success probability)
 * - Timeline filters (age, ETA, development stage)
 * - Text search with fuzzy matching
 * - Active filter indicators with counts
 * - Form validation and error handling
 * - Collapsible sections for organized filter management
 *
 * @component
 * @param {AdvancedSearchFormProps} props - Component properties
 * @returns {JSX.Element} Rendered advanced search form with collapsible filter sections
 *
 * @example
 * ```tsx
 * const [criteria, setCriteria] = useState<AdvancedSearchCriteria>({});
 *
 * <AdvancedSearchForm
 *   criteria={criteria}
 *   onCriteriaChange={(updates) => setCriteria({ ...criteria, ...updates })}
 *   onSearch={handleSearch}
 *   onReset={handleReset}
 *   isLoading={false}
 *   error={null}
 * />
 * ```
 *
 * @since 1.0.0
 * @version 3.4.0
 */
export function AdvancedSearchForm({
  criteria,
  onCriteriaChange,
  onSearch,
  onReset,
  isLoading,
  error
}: AdvancedSearchFormProps) {
  const [expandedSections, setExpandedSections] = useState({
    basic: true,
    statistical: false,
    scouting: false,
    ml: false,
    timeline: false
  });

  const toggleSection = (section: keyof typeof expandedSections) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }));
  };

  const positions = ['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF', 'DH', 'SP', 'RP'];
  const levels = ['MLB', 'AAA', 'AA', 'A+', 'A', 'A-', 'Rookie'];
  const scoutingSources = ['Fangraphs', 'MLB Pipeline', 'Baseball America', 'Baseball Prospectus'];
  const riskLevels = ['Safe', 'Moderate', 'High', 'Extreme'];
  const predictionTypes = ['career_war', 'debut_probability', 'success_rating'];

  const handleArrayFieldChange = (field: keyof AdvancedSearchCriteria, value: string, checked: boolean) => {
    const currentArray = (criteria[field] as string[]) || [];
    const newArray = checked
      ? [...currentArray, value]
      : currentArray.filter(item => item !== value);

    onCriteriaChange({ [field]: newArray });
  };

  const removeArrayValue = (field: keyof AdvancedSearchCriteria, value: string) => {
    const currentArray = (criteria[field] as string[]) || [];
    const newArray = currentArray.filter(item => item !== value);
    onCriteriaChange({ [field]: newArray });
  };

  const getActiveFiltersCount = () => {
    const { page, size, sort_by, ...filters } = criteria;
    return Object.values(filters).filter(value => {
      if (Array.isArray(value)) return value.length > 0;
      return value !== undefined && value !== null && value !== '';
    }).length;
  };

  const activeFiltersCount = getActiveFiltersCount();

  return (
    <div className="space-y-6">
      {/* Search Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Filter className="h-5 w-5 text-gray-500" />
          <span className="text-sm text-gray-600">
            {activeFiltersCount > 0 && (
              <Badge variant="secondary" className="mr-2">
                {activeFiltersCount} active filter{activeFiltersCount !== 1 ? 's' : ''}
              </Badge>
            )}
          </span>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={onReset} disabled={isLoading}>
            Clear All
          </Button>
          <Button onClick={onSearch} disabled={isLoading} className="min-w-[120px]">
            {isLoading ? 'Searching...' : 'Search'}
            <Search className="ml-2 h-4 w-4" />
          </Button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <p className="text-red-800 text-sm">
            Search failed: {error.message || 'Please try again'}
          </p>
        </div>
      )}

      {/* Text Search */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg">Quick Search</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Input
              placeholder="Search by name, organization, or keyword..."
              value={criteria.search_query || ''}
              onChange={(e) => onCriteriaChange({ search_query: e.target.value })}
              className="flex-1"
            />
            <Select
              value={criteria.sort_by || 'relevance'}
              onValueChange={(value) => onCriteriaChange({ sort_by: value })}
            >
              <SelectTrigger className="w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="relevance">Relevance</SelectItem>
                <SelectItem value="name">Name</SelectItem>
                <SelectItem value="age">Age</SelectItem>
                <SelectItem value="eta_year">ETA</SelectItem>
                <SelectItem value="organization">Organization</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Basic Filters */}
      <Collapsible
        open={expandedSections.basic}
        onOpenChange={() => toggleSection('basic')}
      >
        <Card>
          <CollapsibleTrigger asChild>
            <CardHeader className="cursor-pointer hover:bg-gray-50">
              <CardTitle className="flex items-center justify-between text-lg">
                <span className="flex items-center gap-2">
                  <Target className="h-5 w-5 text-blue-500" />
                  Basic Filters
                </span>
                {expandedSections.basic ? (
                  <ChevronDown className="h-4 w-4" />
                ) : (
                  <ChevronRight className="h-4 w-4" />
                )}
              </CardTitle>
            </CardHeader>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <CardContent className="space-y-4">
              {/* Positions */}
              <div>
                <Label className="text-sm font-medium mb-2 block">Positions</Label>
                <div className="flex flex-wrap gap-2">
                  {positions.map((position) => (
                    <div key={position} className="flex items-center space-x-2">
                      <Checkbox
                        id={`position-${position}`}
                        checked={(criteria.positions || []).includes(position)}
                        onCheckedChange={(checked) =>
                          handleArrayFieldChange('positions', position, checked as boolean)
                        }
                      />
                      <Label htmlFor={`position-${position}`} className="text-sm">
                        {position}
                      </Label>
                    </div>
                  ))}
                </div>
                {(criteria.positions || []).length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {criteria.positions?.map((position) => (
                      <Badge key={position} variant="secondary" className="text-xs">
                        {position}
                        <X
                          className="ml-1 h-3 w-3 cursor-pointer"
                          onClick={() => removeArrayValue('positions', position)}
                        />
                      </Badge>
                    ))}
                  </div>
                )}
              </div>

              {/* Levels */}
              <div>
                <Label className="text-sm font-medium mb-2 block">Levels</Label>
                <div className="flex flex-wrap gap-2">
                  {levels.map((level) => (
                    <div key={level} className="flex items-center space-x-2">
                      <Checkbox
                        id={`level-${level}`}
                        checked={(criteria.levels || []).includes(level)}
                        onCheckedChange={(checked) =>
                          handleArrayFieldChange('levels', level, checked as boolean)
                        }
                      />
                      <Label htmlFor={`level-${level}`} className="text-sm">
                        {level}
                      </Label>
                    </div>
                  ))}
                </div>
              </div>

              {/* Age Range */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="min-age" className="text-sm font-medium">Min Age</Label>
                  <Input
                    id="min-age"
                    type="number"
                    min="16"
                    max="35"
                    value={criteria.min_age || ''}
                    onChange={(e) => onCriteriaChange({
                      min_age: e.target.value ? parseInt(e.target.value) : undefined
                    })}
                  />
                </div>
                <div>
                  <Label htmlFor="max-age" className="text-sm font-medium">Max Age</Label>
                  <Input
                    id="max-age"
                    type="number"
                    min="16"
                    max="35"
                    value={criteria.max_age || ''}
                    onChange={(e) => onCriteriaChange({
                      max_age: e.target.value ? parseInt(e.target.value) : undefined
                    })}
                  />
                </div>
              </div>
            </CardContent>
          </CollapsibleContent>
        </Card>
      </Collapsible>

      {/* Statistical Filters */}
      <Collapsible
        open={expandedSections.statistical}
        onOpenChange={() => toggleSection('statistical')}
      >
        <Card>
          <CollapsibleTrigger asChild>
            <CardHeader className="cursor-pointer hover:bg-gray-50">
              <CardTitle className="flex items-center justify-between text-lg">
                <span className="flex items-center gap-2">
                  <BarChart3 className="h-5 w-5 text-green-500" />
                  Statistical Filters
                </span>
                {expandedSections.statistical ? (
                  <ChevronDown className="h-4 w-4" />
                ) : (
                  <ChevronRight className="h-4 w-4" />
                )}
              </CardTitle>
            </CardHeader>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <CardContent className="space-y-4">
              {/* Hitting Stats */}
              <div>
                <h4 className="font-medium mb-3">Hitting Statistics</h4>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="min-batting-avg" className="text-sm">Min Batting Avg</Label>
                    <Input
                      id="min-batting-avg"
                      type="number"
                      step="0.001"
                      min="0"
                      max="1"
                      value={criteria.min_batting_avg || ''}
                      onChange={(e) => onCriteriaChange({
                        min_batting_avg: e.target.value ? parseFloat(e.target.value) : undefined
                      })}
                    />
                  </div>
                  <div>
                    <Label htmlFor="max-batting-avg" className="text-sm">Max Batting Avg</Label>
                    <Input
                      id="max-batting-avg"
                      type="number"
                      step="0.001"
                      min="0"
                      max="1"
                      value={criteria.max_batting_avg || ''}
                      onChange={(e) => onCriteriaChange({
                        max_batting_avg: e.target.value ? parseFloat(e.target.value) : undefined
                      })}
                    />
                  </div>
                  <div>
                    <Label htmlFor="min-obp" className="text-sm">Min OBP</Label>
                    <Input
                      id="min-obp"
                      type="number"
                      step="0.001"
                      min="0"
                      max="1"
                      value={criteria.min_on_base_pct || ''}
                      onChange={(e) => onCriteriaChange({
                        min_on_base_pct: e.target.value ? parseFloat(e.target.value) : undefined
                      })}
                    />
                  </div>
                  <div>
                    <Label htmlFor="min-slugging" className="text-sm">Min Slugging</Label>
                    <Input
                      id="min-slugging"
                      type="number"
                      step="0.001"
                      min="0"
                      max="3"
                      value={criteria.min_slugging_pct || ''}
                      onChange={(e) => onCriteriaChange({
                        min_slugging_pct: e.target.value ? parseFloat(e.target.value) : undefined
                      })}
                    />
                  </div>
                </div>
              </div>

              {/* Pitching Stats */}
              <div>
                <h4 className="font-medium mb-3">Pitching Statistics</h4>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="max-era" className="text-sm">Max ERA</Label>
                    <Input
                      id="max-era"
                      type="number"
                      step="0.01"
                      min="0"
                      max="20"
                      value={criteria.max_era || ''}
                      onChange={(e) => onCriteriaChange({
                        max_era: e.target.value ? parseFloat(e.target.value) : undefined
                      })}
                    />
                  </div>
                  <div>
                    <Label htmlFor="max-whip" className="text-sm">Max WHIP</Label>
                    <Input
                      id="max-whip"
                      type="number"
                      step="0.01"
                      min="0"
                      max="5"
                      value={criteria.max_whip || ''}
                      onChange={(e) => onCriteriaChange({
                        max_whip: e.target.value ? parseFloat(e.target.value) : undefined
                      })}
                    />
                  </div>
                </div>
              </div>
            </CardContent>
          </CollapsibleContent>
        </Card>
      </Collapsible>

      {/* Scouting Filters */}
      <Collapsible
        open={expandedSections.scouting}
        onOpenChange={() => toggleSection('scouting')}
      >
        <Card>
          <CollapsibleTrigger asChild>
            <CardHeader className="cursor-pointer hover:bg-gray-50">
              <CardTitle className="flex items-center justify-between text-lg">
                <span className="flex items-center gap-2">
                  <Target className="h-5 w-5 text-orange-500" />
                  Scouting Filters
                </span>
                {expandedSections.scouting ? (
                  <ChevronDown className="h-4 w-4" />
                ) : (
                  <ChevronRight className="h-4 w-4" />
                )}
              </CardTitle>
            </CardHeader>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <CardContent className="space-y-4">
              {/* Overall Grade */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="min-overall-grade" className="text-sm">Min Overall Grade</Label>
                  <Input
                    id="min-overall-grade"
                    type="number"
                    min="20"
                    max="80"
                    value={criteria.min_overall_grade || ''}
                    onChange={(e) => onCriteriaChange({
                      min_overall_grade: e.target.value ? parseInt(e.target.value) : undefined
                    })}
                  />
                </div>
                <div>
                  <Label htmlFor="max-overall-grade" className="text-sm">Max Overall Grade</Label>
                  <Input
                    id="max-overall-grade"
                    type="number"
                    min="20"
                    max="80"
                    value={criteria.max_overall_grade || ''}
                    onChange={(e) => onCriteriaChange({
                      max_overall_grade: e.target.value ? parseInt(e.target.value) : undefined
                    })}
                  />
                </div>
              </div>

              {/* Risk Levels */}
              <div>
                <Label className="text-sm font-medium mb-2 block">Risk Levels</Label>
                <div className="flex gap-4">
                  {riskLevels.map((risk) => (
                    <div key={risk} className="flex items-center space-x-2">
                      <Checkbox
                        id={`risk-${risk}`}
                        checked={(criteria.risk_levels || []).includes(risk)}
                        onCheckedChange={(checked) =>
                          handleArrayFieldChange('risk_levels', risk, checked as boolean)
                        }
                      />
                      <Label htmlFor={`risk-${risk}`} className="text-sm">
                        {risk}
                      </Label>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </CollapsibleContent>
        </Card>
      </Collapsible>

      {/* ML Prediction Filters */}
      <Collapsible
        open={expandedSections.ml}
        onOpenChange={() => toggleSection('ml')}
      >
        <Card>
          <CollapsibleTrigger asChild>
            <CardHeader className="cursor-pointer hover:bg-gray-50">
              <CardTitle className="flex items-center justify-between text-lg">
                <span className="flex items-center gap-2">
                  <Brain className="h-5 w-5 text-purple-500" />
                  ML Prediction Filters
                </span>
                {expandedSections.ml ? (
                  <ChevronDown className="h-4 w-4" />
                ) : (
                  <ChevronRight className="h-4 w-4" />
                )}
              </CardTitle>
            </CardHeader>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="min-success-prob" className="text-sm">Min Success Probability</Label>
                  <Input
                    id="min-success-prob"
                    type="number"
                    step="0.01"
                    min="0"
                    max="1"
                    value={criteria.min_success_probability || ''}
                    onChange={(e) => onCriteriaChange({
                      min_success_probability: e.target.value ? parseFloat(e.target.value) : undefined
                    })}
                  />
                </div>
                <div>
                  <Label htmlFor="min-confidence" className="text-sm">Min Confidence Score</Label>
                  <Input
                    id="min-confidence"
                    type="number"
                    step="0.01"
                    min="0"
                    max="1"
                    value={criteria.min_confidence_score || ''}
                    onChange={(e) => onCriteriaChange({
                      min_confidence_score: e.target.value ? parseFloat(e.target.value) : undefined
                    })}
                  />
                </div>
              </div>
            </CardContent>
          </CollapsibleContent>
        </Card>
      </Collapsible>
    </div>
  );
}