/**
 * Profile Tab Component
 *
 * Displays user profile information and allows editing of personal details.
 * Shows account metadata and provides logout functionality.
 *
 * @component ProfileTab
 * @since 1.0.0
 */

'use client';

import React, { useState, useEffect } from 'react';
import Image from 'next/image';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useAuth } from '@/hooks/useAuth';
import { AuthAPI, type UserProfile } from '@/lib/auth/api';
import {
  User,
  Mail,
  Calendar,
  Loader2,
  CheckCircle2,
  LogOut,
  AlertCircle,
} from 'lucide-react';

/**
 * Profile tab for account management
 *
 * @returns {JSX.Element} Rendered profile management interface
 *
 * @example
 * ```tsx
 * <ProfileTab />
 * ```
 *
 * @since 1.0.0
 */
export function ProfileTab(): JSX.Element {
  const { user, logout } = useAuth();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [fullName, setFullName] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isFetching, setIsFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    fetchProfile();
  }, []);

  /**
   * Fetch user profile from API
   */
  const fetchProfile = async () => {
    try {
      setIsFetching(true);
      setError(null);
      const profileData = await AuthAPI.getUserProfile();
      setProfile(profileData);
      setFullName(profileData.full_name || '');
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load profile';
      setError(errorMessage);
    } finally {
      setIsFetching(false);
    }
  };

  /**
   * Update user profile
   */
  const handleUpdateProfile = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!fullName.trim()) {
      setError('Full name is required');
      return;
    }

    if (fullName.trim().length < 2) {
      setError('Full name must be at least 2 characters');
      return;
    }

    setIsLoading(true);
    setError(null);
    setSuccess(false);

    try {
      const updatedProfile = await AuthAPI.updateProfile({
        full_name: fullName,
        preferences: profile?.preferences,
      });

      setProfile(updatedProfile);
      setSuccess(true);

      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to update profile';
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Handle logout
   */
  const handleLogout = async () => {
    if (confirm('Are you sure you want to log out?')) {
      try {
        await logout();
      } catch (err) {
        console.error('Logout failed:', err);
        // Force logout even if API call fails
        window.location.href = '/login';
      }
    }
  };

  if (isFetching) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
          <span className="ml-2 text-gray-600">Loading profile...</span>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Account Information Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <User className="h-5 w-5" />
            Account Information
          </CardTitle>
          <CardDescription>View your account details and membership status</CardDescription>
        </CardHeader>
        <CardContent>
          {profile && (
            <div className="space-y-4">
              {/* Profile Picture */}
              {profile.profile_picture && (
                <div className="flex items-center gap-4 pb-4 border-b">
                  <Image
                    src={profile.profile_picture}
                    alt="Profile"
                    width={64}
                    height={64}
                    className="w-16 h-16 rounded-full border-2 border-gray-200"
                  />
                  <div>
                    <p className="font-medium text-gray-900">{profile.full_name || 'Not set'}</p>
                    <p className="text-sm text-gray-600">{profile.email}</p>
                  </div>
                </div>
              )}

              {/* Account Details Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-4 bg-gray-50 rounded-lg">
                  <div className="flex items-center gap-2 text-gray-600 mb-1">
                    <Mail className="h-4 w-4" />
                    <span className="text-sm font-medium">Email Address</span>
                  </div>
                  <p className="font-medium text-gray-900">{profile.email}</p>
                </div>

                <div className="p-4 bg-gray-50 rounded-lg">
                  <div className="flex items-center gap-2 text-gray-600 mb-1">
                    <User className="h-4 w-4" />
                    <span className="text-sm font-medium">Account Type</span>
                  </div>
                  <Badge variant={profile.google_id ? 'default' : 'secondary'}>
                    {profile.google_id ? 'Google Account' : 'Email Account'}
                  </Badge>
                </div>

                <div className="p-4 bg-gray-50 rounded-lg">
                  <div className="flex items-center gap-2 text-gray-600 mb-1">
                    <Calendar className="h-4 w-4" />
                    <span className="text-sm font-medium">Member Since</span>
                  </div>
                  <p className="font-medium text-gray-900">
                    {new Date(profile.created_at).toLocaleDateString('en-US', {
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric',
                    })}
                  </p>
                </div>

                <div className="p-4 bg-gray-50 rounded-lg">
                  <div className="flex items-center gap-2 text-gray-600 mb-1">
                    <CheckCircle2 className="h-4 w-4" />
                    <span className="text-sm font-medium">Subscription</span>
                  </div>
                  <Badge
                    variant={user?.subscription_tier === 'premium' ? 'default' : 'secondary'}
                  >
                    {user?.subscription_tier === 'premium' ? 'Premium' : 'Free'}
                  </Badge>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Edit Profile Card */}
      <Card>
        <CardHeader>
          <CardTitle>Personal Information</CardTitle>
          <CardDescription>Update your personal details</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleUpdateProfile} className="space-y-6">
            {/* Full Name Field */}
            <div className="space-y-2">
              <Label htmlFor="full_name">Full Name</Label>
              <Input
                id="full_name"
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Enter your full name"
                disabled={isLoading}
              />
            </div>

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
                <AlertDescription>Profile updated successfully!</AlertDescription>
              </Alert>
            )}

            {/* Action Buttons */}
            <div className="flex gap-4">
              <Button type="submit" disabled={isLoading} className="flex-1">
                {isLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Updating...
                  </>
                ) : (
                  'Update Profile'
                )}
              </Button>

              <Button
                type="button"
                variant="outline"
                onClick={fetchProfile}
                disabled={isLoading || isFetching}
              >
                Reset
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Account Actions Card */}
      <Card>
        <CardHeader>
          <CardTitle>Account Actions</CardTitle>
          <CardDescription>Manage your account and session</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
              <div>
                <p className="font-medium text-gray-900">Sign Out</p>
                <p className="text-sm text-gray-600">End your current session</p>
              </div>
              <Button variant="outline" onClick={handleLogout}>
                <LogOut className="mr-2 h-4 w-4" />
                Log Out
              </Button>
            </div>

            <div className="text-xs text-gray-500 text-center pt-4 border-t">
              <p>Last updated: {profile ? new Date(profile.updated_at).toLocaleString() : '-'}</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
