/**
 * Email preferences management component.
 *
 * @component EmailPreferences
 * @module EmailPreferences
 * @since 1.0.0
 */

'use client';

import React, { useState } from 'react';
import { useEmailPreferences } from '@/hooks/useEmailPreferences';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, Mail, CheckCircle, AlertCircle } from 'lucide-react';

/**
 * Props for EmailPreferences component.
 *
 * @interface EmailPreferencesProps
 * @since 1.0.0
 */
export interface EmailPreferencesProps {
  /** Optional CSS class name */
  className?: string;
}

/**
 * Email preferences management component.
 *
 * Allows users to configure email digest settings including frequency,
 * enable/disable status, and preview digest content.
 *
 * @param {EmailPreferencesProps} props - Component props
 * @returns {JSX.Element} Rendered email preferences interface
 *
 * @example
 * ```tsx
 * <EmailPreferences className="max-w-2xl mx-auto" />
 * ```
 *
 * @since 1.0.0
 */
export function EmailPreferences({
  className,
}: EmailPreferencesProps): JSX.Element {
  const {
    preferences,
    isLoading,
    error,
    isUpdating,
    isPreviewing,
    previewContent,
    updatePreferences,
    loadPreview,
  } = useEmailPreferences();

  const [showSuccess, setShowSuccess] = useState(false);

  /**
   * Handle digest enabled toggle.
   *
   * @param enabled - New enabled state
   * @since 1.0.0
   */
  const handleToggleDigest = async (enabled: boolean): Promise<void> => {
    try {
      await updatePreferences({ digest_enabled: enabled });
      setShowSuccess(true);
      setTimeout(() => setShowSuccess(false), 3000);
    } catch (err) {
      console.error('Failed to toggle digest:', err);
    }
  };

  /**
   * Handle frequency change.
   *
   * @param frequency - New frequency value
   * @since 1.0.0
   */
  const handleFrequencyChange = async (
    frequency: 'daily' | 'weekly' | 'monthly'
  ): Promise<void> => {
    try {
      await updatePreferences({ frequency });
      setShowSuccess(true);
      setTimeout(() => setShowSuccess(false), 3000);
    } catch (err) {
      console.error('Failed to update frequency:', err);
    }
  };

  /**
   * Handle preview button click.
   *
   * @since 1.0.0
   */
  const handlePreview = async (): Promise<void> => {
    try {
      await loadPreview();
    } catch (err) {
      console.error('Failed to load preview:', err);
    }
  };

  if (isLoading) {
    return (
      <div
        className={`flex items-center justify-center p-8 ${className || ''}`}
      >
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive" className={className}>
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>
          Failed to load email preferences. Please try again later.
        </AlertDescription>
      </Alert>
    );
  }

  if (!preferences) {
    return null;
  }

  return (
    <div className={className}>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Mail className="h-5 w-5" />
            Email Digest Settings
          </CardTitle>
          <CardDescription>
            Configure your weekly prospect update emails
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Success message */}
          {showSuccess && (
            <Alert className="bg-green-50 border-green-200">
              <CheckCircle className="h-4 w-4 text-green-600" />
              <AlertDescription className="text-green-800">
                Preferences updated successfully
              </AlertDescription>
            </Alert>
          )}

          {/* Enable/Disable digest */}
          <div className="flex items-center justify-between space-x-4">
            <div className="flex-1">
              <Label htmlFor="digest-enabled" className="text-base font-medium">
                Email Digest
              </Label>
              <p className="text-sm text-muted-foreground mt-1">
                Receive personalized prospect updates via email
              </p>
            </div>
            <Switch
              id="digest-enabled"
              checked={preferences.digest_enabled}
              onCheckedChange={handleToggleDigest}
              disabled={isUpdating}
            />
          </div>

          {/* Frequency selector */}
          {preferences.digest_enabled && (
            <div className="space-y-2">
              <Label htmlFor="frequency" className="text-base font-medium">
                Frequency
              </Label>
              <Select
                value={preferences.frequency}
                onValueChange={handleFrequencyChange}
                disabled={isUpdating}
              >
                <SelectTrigger id="frequency" className="w-full">
                  <SelectValue placeholder="Select frequency" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="daily">Daily</SelectItem>
                  <SelectItem value="weekly">
                    Weekly (Monday mornings)
                  </SelectItem>
                  <SelectItem value="monthly">
                    Monthly (First Monday)
                  </SelectItem>
                </SelectContent>
              </Select>
              <p className="text-sm text-muted-foreground">
                {preferences.frequency === 'daily' &&
                  "You'll receive a digest every morning at 7 AM"}
                {preferences.frequency === 'weekly' &&
                  "You'll receive a digest every Monday at 6 AM"}
                {preferences.frequency === 'monthly' &&
                  "You'll receive a digest on the first Monday of each month"}
              </p>
            </div>
          )}

          {/* Last sent info */}
          {preferences.last_sent && (
            <div className="text-sm text-muted-foreground">
              <p>
                Last digest sent:{' '}
                <span className="font-medium">
                  {new Date(preferences.last_sent).toLocaleDateString('en-US', {
                    weekday: 'long',
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric',
                  })}
                </span>
              </p>
            </div>
          )}

          {/* Preview button */}
          {preferences.digest_enabled && (
            <div className="pt-4 border-t">
              <Button
                variant="outline"
                onClick={handlePreview}
                disabled={isPreviewing}
                className="w-full"
              >
                {isPreviewing ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Generating Preview...
                  </>
                ) : (
                  <>
                    <Mail className="mr-2 h-4 w-4" />
                    Preview Next Digest
                  </>
                )}
              </Button>
            </div>
          )}

          {/* Preview content */}
          {previewContent && previewContent.content && (
            <div className="mt-4 p-4 bg-muted rounded-lg space-y-3">
              <h4 className="font-medium">Digest Preview</h4>
              <div className="text-sm space-y-2">
                <p>
                  <span className="font-medium">Watchlist Updates:</span>{' '}
                  {previewContent.content.watchlist_updates.length} prospects
                </p>
                <p>
                  <span className="font-medium">Top Movers:</span>{' '}
                  {previewContent.content.top_movers.length} prospects
                </p>
                <p>
                  <span className="font-medium">Recommendations:</span>{' '}
                  {previewContent.content.recommendations.length} prospects
                </p>
              </div>
            </div>
          )}

          {previewContent && !previewContent.content && (
            <Alert>
              <AlertDescription>{previewContent.message}</AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default EmailPreferences;
