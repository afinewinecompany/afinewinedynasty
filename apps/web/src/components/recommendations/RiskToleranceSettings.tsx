/**
 * Risk Tolerance Settings Component
 *
 * Allows users to configure recommendation preferences including risk tolerance,
 * timeline preferences, position priorities, and trade preferences.
 *
 * @component RiskToleranceSettings
 * @since 1.0.0
 */

'use client';

import React, { useEffect, useState } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Loader2,
  Settings,
  TrendingUp,
  TrendingDown,
  Shield,
  Zap,
  Activity,
} from 'lucide-react';
import { useRecommendations } from '@/hooks/useRecommendations';
import type { UserPreferences } from '@/types/recommendations';

/**
 * Component props
 */
interface RiskToleranceSettingsProps {
  /** Whether to auto-load preferences on mount */
  autoLoad?: boolean;
  /** Optional callback when preferences are saved */
  onSave?: (preferences: UserPreferences) => void;
}

/**
 * Risk tolerance settings component
 *
 * @param props - Component props
 * @returns Rendered component
 *
 * @example
 * ```tsx
 * <RiskToleranceSettings
 *   autoLoad={true}
 *   onSave={(prefs) => console.log('Saved:', prefs)}
 * />
 * ```
 *
 * @since 1.0.0
 */
export function RiskToleranceSettings({
  autoLoad = true,
  onSave,
}: RiskToleranceSettingsProps) {
  const { preferences, loading, error, fetchPreferences, updatePreferences } =
    useRecommendations();

  // Local form state
  const [formData, setFormData] = useState<UserPreferences>({
    risk_tolerance: 'balanced',
    prefer_win_now: false,
    prefer_rebuild: false,
    position_priorities: [],
    prefer_buy_low: false,
    prefer_sell_high: false,
  });

  const [hasChanges, setHasChanges] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Auto-load on mount
  useEffect(() => {
    if (autoLoad) {
      fetchPreferences();
    }
  }, [autoLoad, fetchPreferences]);

  // Update form when preferences load
  useEffect(() => {
    if (preferences) {
      setFormData(preferences);
      setHasChanges(false);
    }
  }, [preferences]);

  /**
   * Get risk tolerance icon and description
   */
  const getRiskToleranceInfo = (
    tolerance: UserPreferences['risk_tolerance']
  ) => {
    const info = {
      conservative: {
        icon: Shield,
        label: 'Conservative',
        description: 'Prioritize proven prospects with safer floors',
        color: 'text-blue-600',
      },
      balanced: {
        icon: Activity,
        label: 'Balanced',
        description: 'Mix of safe and high-upside prospects',
        color: 'text-green-600',
      },
      aggressive: {
        icon: Zap,
        label: 'Aggressive',
        description: 'Focus on high-ceiling prospects with breakout potential',
        color: 'text-orange-600',
      },
    };
    return info[tolerance];
  };

  /**
   * Available positions for selection
   */
  const positions = ['SP', 'RP', 'C', '1B', '2B', '3B', 'SS', 'OF', 'DH'];

  /**
   * Handle form field change
   */
  const handleChange = (field: keyof UserPreferences, value: any) => {
    setFormData((prev) => ({
      ...prev,
      [field]: value,
    }));
    setHasChanges(true);
    setSaveSuccess(false);
  };

  /**
   * Toggle position priority
   */
  const togglePosition = (position: string) => {
    const current = formData.position_priorities;
    const updated = current.includes(position)
      ? current.filter((p) => p !== position)
      : [...current, position];
    handleChange('position_priorities', updated);
  };

  /**
   * Handle save
   */
  const handleSave = async () => {
    try {
      await updatePreferences(formData);
      setHasChanges(false);
      setSaveSuccess(true);
      onSave?.(formData);

      // Clear success message after 3 seconds
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err) {
      // Error already handled by hook
      console.error('Failed to save preferences:', err);
    }
  };

  /**
   * Handle reset
   */
  const handleReset = () => {
    if (preferences) {
      setFormData(preferences);
      setHasChanges(false);
      setSaveSuccess(false);
    }
  };

  if (loading.preferences && !preferences) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
          <span className="ml-2 text-gray-600">Loading preferences...</span>
        </CardContent>
      </Card>
    );
  }

  const riskInfo = getRiskToleranceInfo(formData.risk_tolerance);
  const RiskIcon = riskInfo.icon;

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Settings className="h-5 w-5" />
              Recommendation Preferences
            </CardTitle>
            <CardDescription>
              Customize how prospects are recommended to you
            </CardDescription>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Error Alert */}
        {error.preferences && (
          <Alert variant="destructive">
            <AlertDescription>{error.preferences}</AlertDescription>
          </Alert>
        )}

        {/* Success Alert */}
        {saveSuccess && (
          <Alert>
            <AlertDescription className="text-green-700">
              Preferences saved successfully!
            </AlertDescription>
          </Alert>
        )}

        {/* Risk Tolerance */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Risk Tolerance
          </label>
          <Select
            value={formData.risk_tolerance}
            onValueChange={(value) =>
              handleChange(
                'risk_tolerance',
                value as UserPreferences['risk_tolerance']
              )
            }
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="conservative">Conservative</SelectItem>
              <SelectItem value="balanced">Balanced</SelectItem>
              <SelectItem value="aggressive">Aggressive</SelectItem>
            </SelectContent>
          </Select>
          <div className="mt-3 p-3 rounded-lg bg-gray-50 border border-gray-200">
            <div className="flex items-center gap-2 mb-1">
              <RiskIcon className={`h-4 w-4 ${riskInfo.color}`} />
              <span className="text-sm font-medium text-gray-900">
                {riskInfo.label}
              </span>
            </div>
            <p className="text-xs text-gray-600">{riskInfo.description}</p>
          </div>
        </div>

        {/* Timeline Preferences */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-3">
            Competitive Timeline
          </label>
          <div className="space-y-2">
            <Checkbox
              checked={formData.prefer_win_now}
              onChange={(e) => handleChange('prefer_win_now', e.target.checked)}
              label="Prioritize win-now prospects (near-MLB ready)"
            />
            <Checkbox
              checked={formData.prefer_rebuild}
              onChange={(e) => handleChange('prefer_rebuild', e.target.checked)}
              label="Prioritize rebuild prospects (long-term upside)"
            />
          </div>
          <p className="text-xs text-gray-500 mt-2">
            Select your team's competitive window to receive more targeted
            recommendations
          </p>
        </div>

        {/* Position Priorities */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-3">
            Position Priorities
          </label>
          <div className="flex flex-wrap gap-2">
            {positions.map((position) => {
              const isSelected =
                formData.position_priorities.includes(position);
              return (
                <Badge
                  key={position}
                  className={`cursor-pointer transition-colors ${
                    isSelected
                      ? 'bg-blue-600 text-white hover:bg-blue-700'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                  onClick={() => togglePosition(position)}
                >
                  {position}
                </Badge>
              );
            })}
          </div>
          <p className="text-xs text-gray-500 mt-2">
            Click positions to prioritize them in recommendations (multi-select)
          </p>
        </div>

        {/* Trade Preferences */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-3">
            Trade Preferences
          </label>
          <div className="space-y-2">
            <Checkbox
              checked={formData.prefer_buy_low}
              onChange={(e) => handleChange('prefer_buy_low', e.target.checked)}
              label={
                <span className="flex items-center gap-1">
                  <TrendingDown className="h-3 w-3" />
                  Highlight buy-low opportunities
                </span>
              }
            />
            <Checkbox
              checked={formData.prefer_sell_high}
              onChange={(e) =>
                handleChange('prefer_sell_high', e.target.checked)
              }
              label={
                <span className="flex items-center gap-1">
                  <TrendingUp className="h-3 w-3" />
                  Highlight sell-high opportunities
                </span>
              }
            />
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-3 pt-4 border-t border-gray-200">
          <Button
            onClick={handleSave}
            disabled={!hasChanges || loading.preferences}
            className="flex-1"
          >
            {loading.preferences ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              'Save Preferences'
            )}
          </Button>
          <Button
            variant="outline"
            onClick={handleReset}
            disabled={!hasChanges}
          >
            Reset
          </Button>
        </div>

        {/* Info Note */}
        <div className="p-3 rounded-lg bg-blue-50 border border-blue-200">
          <p className="text-xs text-blue-700">
            These preferences will be used to personalize your prospect
            recommendations, trade targets, and draft strategy across the
            platform.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
