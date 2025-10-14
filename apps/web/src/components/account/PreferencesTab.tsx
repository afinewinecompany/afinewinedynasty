/**
 * Preferences Tab Component
 *
 * Allows users to customize their experience including theme, notifications,
 * email preferences, and display settings.
 *
 * @component PreferencesTab
 * @since 1.0.0
 */

'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Label } from '@/components/ui/label';
import { AuthAPI } from '@/lib/auth/api';
import {
  Sun,
  Moon,
  Monitor,
  Bell,
  Mail,
  Eye,
  CheckCircle2,
  AlertCircle,
  Loader2,
} from 'lucide-react';

/**
 * User preferences interface
 */
interface UserPreferences {
  theme: 'light' | 'dark' | 'auto';
  notifications: boolean;
  marketing_emails: boolean;
  newsletter: boolean;
  compact_view: boolean;
  show_percentiles: boolean;
}

/**
 * Preferences management tab
 *
 * @returns {JSX.Element} Rendered preferences interface
 *
 * @example
 * ```tsx
 * <PreferencesTab />
 * ```
 *
 * @since 1.0.0
 */
export function PreferencesTab(): JSX.Element {
  const [preferences, setPreferences] = useState<UserPreferences>({
    theme: 'light',
    notifications: true,
    marketing_emails: false,
    newsletter: false,
    compact_view: false,
    show_percentiles: true,
  });

  const [isLoading, setIsLoading] = useState(false);
  const [isFetching, setIsFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    fetchPreferences();
  }, []);

  /**
   * Fetch user preferences
   */
  const fetchPreferences = async () => {
    try {
      setIsFetching(true);
      setError(null);
      const profile = await AuthAPI.getUserProfile();

      if (profile.preferences) {
        setPreferences({
          theme: profile.preferences.theme || 'light',
          notifications: profile.preferences.notifications ?? true,
          marketing_emails: profile.preferences.marketing_emails ?? false,
          newsletter: profile.preferences.newsletter ?? false,
          compact_view: profile.preferences.compact_view ?? false,
          show_percentiles: profile.preferences.show_percentiles ?? true,
        });
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load preferences';
      setError(errorMessage);
    } finally {
      setIsFetching(false);
    }
  };

  /**
   * Update preferences
   */
  const handleSavePreferences = async () => {
    setIsLoading(true);
    setError(null);
    setSuccess(false);

    try {
      await AuthAPI.updateProfile({
        preferences,
      });

      setSuccess(true);

      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to save preferences';
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Update a single preference
   */
  const updatePreference = (key: keyof UserPreferences, value: any) => {
    setPreferences((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  if (isFetching) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
          <span className="ml-2 text-gray-600">Loading preferences...</span>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Appearance Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sun className="h-5 w-5" />
            Appearance
          </CardTitle>
          <CardDescription>Customize how the application looks</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label className="text-base mb-3 block">Theme</Label>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <button
                onClick={() => updatePreference('theme', 'light')}
                className={`p-4 border-2 rounded-lg transition-all hover:shadow-md ${
                  preferences.theme === 'light'
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <Sun className="h-6 w-6 mx-auto mb-2 text-yellow-500" />
                <p className="font-medium text-sm">Light</p>
                <p className="text-xs text-gray-600">Classic bright theme</p>
              </button>

              <button
                onClick={() => updatePreference('theme', 'dark')}
                className={`p-4 border-2 rounded-lg transition-all hover:shadow-md ${
                  preferences.theme === 'dark'
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <Moon className="h-6 w-6 mx-auto mb-2 text-indigo-500" />
                <p className="font-medium text-sm">Dark</p>
                <p className="text-xs text-gray-600">Easy on the eyes</p>
              </button>

              <button
                onClick={() => updatePreference('theme', 'auto')}
                className={`p-4 border-2 rounded-lg transition-all hover:shadow-md ${
                  preferences.theme === 'auto'
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <Monitor className="h-6 w-6 mx-auto mb-2 text-gray-500" />
                <p className="font-medium text-sm">Auto</p>
                <p className="text-xs text-gray-600">Match system settings</p>
              </button>
            </div>
          </div>

          <div className="pt-4 border-t">
            <Label className="text-base mb-3 block">Display Options</Label>
            <div className="space-y-3">
              <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div className="flex items-center gap-3">
                  <Eye className="h-5 w-5 text-gray-600" />
                  <div>
                    <p className="font-medium text-sm">Compact View</p>
                    <p className="text-xs text-gray-600">Show more data in less space</p>
                  </div>
                </div>
                <button
                  onClick={() => updatePreference('compact_view', !preferences.compact_view)}
                  className={`relative w-12 h-6 rounded-full transition-colors ${
                    preferences.compact_view ? 'bg-blue-600' : 'bg-gray-300'
                  }`}
                >
                  <div
                    className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${
                      preferences.compact_view ? 'translate-x-6' : 'translate-x-0'
                    }`}
                  />
                </button>
              </div>

              <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div className="flex items-center gap-3">
                  <Eye className="h-5 w-5 text-gray-600" />
                  <div>
                    <p className="font-medium text-sm">Show Percentiles</p>
                    <p className="text-xs text-gray-600">Display percentile rankings</p>
                  </div>
                </div>
                <button
                  onClick={() => updatePreference('show_percentiles', !preferences.show_percentiles)}
                  className={`relative w-12 h-6 rounded-full transition-colors ${
                    preferences.show_percentiles ? 'bg-blue-600' : 'bg-gray-300'
                  }`}
                >
                  <div
                    className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${
                      preferences.show_percentiles ? 'translate-x-6' : 'translate-x-0'
                    }`}
                  />
                </button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Notifications Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bell className="h-5 w-5" />
            Notifications
          </CardTitle>
          <CardDescription>Control how we notify you about updates</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <div className="flex items-center gap-3">
              <Bell className="h-5 w-5 text-gray-600" />
              <div>
                <p className="font-medium text-sm">Push Notifications</p>
                <p className="text-xs text-gray-600">
                  Get notified about prospect updates and rankings changes
                </p>
              </div>
            </div>
            <button
              onClick={() => updatePreference('notifications', !preferences.notifications)}
              className={`relative w-12 h-6 rounded-full transition-colors ${
                preferences.notifications ? 'bg-blue-600' : 'bg-gray-300'
              }`}
            >
              <div
                className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${
                  preferences.notifications ? 'translate-x-6' : 'translate-x-0'
                }`}
              />
            </button>
          </div>
        </CardContent>
      </Card>

      {/* Email Preferences */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Mail className="h-5 w-5" />
            Email Preferences
          </CardTitle>
          <CardDescription>Manage your email subscriptions</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <div className="flex items-center gap-3">
              <Mail className="h-5 w-5 text-gray-600" />
              <div>
                <p className="font-medium text-sm">Weekly Newsletter</p>
                <p className="text-xs text-gray-600">
                  Weekly prospect updates and analysis
                </p>
              </div>
            </div>
            <button
              onClick={() => updatePreference('newsletter', !preferences.newsletter)}
              className={`relative w-12 h-6 rounded-full transition-colors ${
                preferences.newsletter ? 'bg-blue-600' : 'bg-gray-300'
              }`}
            >
              <div
                className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${
                  preferences.newsletter ? 'translate-x-6' : 'translate-x-0'
                }`}
              />
            </button>
          </div>

          <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <div className="flex items-center gap-3">
              <Mail className="h-5 w-5 text-gray-600" />
              <div>
                <p className="font-medium text-sm">Marketing Emails</p>
                <p className="text-xs text-gray-600">
                  Product updates and special offers
                </p>
              </div>
            </div>
            <button
              onClick={() => updatePreference('marketing_emails', !preferences.marketing_emails)}
              className={`relative w-12 h-6 rounded-full transition-colors ${
                preferences.marketing_emails ? 'bg-blue-600' : 'bg-gray-300'
              }`}
            >
              <div
                className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${
                  preferences.marketing_emails ? 'translate-x-6' : 'translate-x-0'
                }`}
              />
            </button>
          </div>
        </CardContent>
      </Card>

      {/* Error Display */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Success Display */}
      {success && (
        <Alert className="bg-green-50 text-green-900 border-green-200">
          <CheckCircle2 className="h-4 w-4 text-green-600" />
          <AlertDescription>Preferences saved successfully!</AlertDescription>
        </Alert>
      )}

      {/* Save Button */}
      <div className="flex gap-4">
        <Button onClick={handleSavePreferences} disabled={isLoading} className="flex-1">
          {isLoading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Saving...
            </>
          ) : (
            <>
              <CheckCircle2 className="mr-2 h-4 w-4" />
              Save Preferences
            </>
          )}
        </Button>

        <Button
          variant="outline"
          onClick={fetchPreferences}
          disabled={isLoading || isFetching}
        >
          Reset
        </Button>
      </div>
    </div>
  );
}
