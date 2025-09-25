'use client';

import React, { useState, useEffect } from 'react';
import { AuthAPI, type UserProfile } from '@/lib/auth/api';

interface ProfileFormProps {
  onSuccess?: (profile: UserProfile) => void;
  onError?: (error: string) => void;
}

interface FormData {
  full_name: string;
  preferences: {
    theme: string;
    notifications: boolean;
    marketing_emails: boolean;
  };
}

interface FormErrors {
  full_name?: string;
  general?: string;
}

export function ProfileForm({ onSuccess, onError }: ProfileFormProps) {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [formData, setFormData] = useState<FormData>({
    full_name: '',
    preferences: {
      theme: 'light',
      notifications: true,
      marketing_emails: false,
    },
  });
  const [errors, setErrors] = useState<FormErrors>({});
  const [isLoading, setIsLoading] = useState(false);
  const [isFetching, setIsFetching] = useState(true);

  useEffect(() => {
    fetchProfile();
  }, []);

  const fetchProfile = async () => {
    try {
      setIsFetching(true);
      const profileData = await AuthAPI.getUserProfile();
      setProfile(profileData);
      setFormData({
        full_name: profileData.full_name || '',
        preferences: {
          theme: profileData.preferences?.theme || 'light',
          notifications: profileData.preferences?.notifications ?? true,
          marketing_emails: profileData.preferences?.marketing_emails ?? false,
        },
      });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to load profile';
      setErrors({ general: errorMessage });
      onError?.(errorMessage);
    } finally {
      setIsFetching(false);
    }
  };

  const validateForm = (): boolean => {
    const newErrors: FormErrors = {};

    if (!formData.full_name.trim()) {
      newErrors.full_name = 'Full name is required';
    } else if (formData.full_name.trim().length < 2) {
      newErrors.full_name = 'Full name must be at least 2 characters';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target;

    if (name.startsWith('preferences.')) {
      const prefKey = name.split('.')[1];
      setFormData(prev => ({
        ...prev,
        preferences: {
          ...prev.preferences,
          [prefKey]: type === 'checkbox' ? (e.target as HTMLInputElement).checked : value,
        },
      }));
    } else {
      setFormData(prev => ({ ...prev, [name]: value }));
    }

    // Clear specific field error when user starts typing
    if (errors[name as keyof FormErrors]) {
      setErrors(prev => ({ ...prev, [name]: undefined }));
    }
  };

  const handleCheckboxChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, checked } = e.target;
    const prefKey = name.split('.')[1];

    setFormData(prev => ({
      ...prev,
      preferences: {
        ...prev.preferences,
        [prefKey]: checked,
      },
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    setIsLoading(true);

    try {
      const updatedProfile = await AuthAPI.updateProfile({
        full_name: formData.full_name,
        preferences: formData.preferences,
      });

      setProfile(updatedProfile);
      onSuccess?.(updatedProfile);

      // Show success message
      setErrors({ general: undefined });
      alert('Profile updated successfully!');
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Profile update failed';
      setErrors({ general: errorMessage });
      onError?.(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const handleLogout = async () => {
    try {
      await AuthAPI.logout();
      // Redirect to login page or trigger parent component logout
      window.location.href = '/';
    } catch (error) {
      console.error('Logout failed:', error);
      // Even if logout request fails, clear local tokens
      window.location.href = '/';
    }
  };

  if (isFetching) {
    return (
      <div className="max-w-2xl mx-auto bg-white p-8 border border-gray-300 rounded-lg shadow-lg">
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-1/4 mb-4"></div>
          <div className="h-4 bg-gray-200 rounded w-1/2 mb-2"></div>
          <div className="h-4 bg-gray-200 rounded w-3/4 mb-6"></div>
          <div className="h-10 bg-gray-200 rounded mb-4"></div>
          <div className="h-10 bg-gray-200 rounded mb-4"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto bg-white p-8 border border-gray-300 rounded-lg shadow-lg">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-gray-900">Profile Settings</h2>
        <button
          type="button"
          onClick={handleLogout}
          className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 border border-gray-300 rounded-md hover:bg-gray-50"
        >
          Logout
        </button>
      </div>

      {profile && (
        <div className="mb-6 p-4 bg-gray-50 rounded-lg">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div>
              <strong>Email:</strong> {profile.email}
            </div>
            <div>
              <strong>Account Type:</strong> {profile.google_id ? 'Google Account' : 'Email Account'}
            </div>
            <div>
              <strong>Member Since:</strong> {new Date(profile.created_at).toLocaleDateString()}
            </div>
            <div>
              <strong>Last Updated:</strong> {new Date(profile.updated_at).toLocaleDateString()}
            </div>
          </div>
          {profile.profile_picture && (
            <div className="mt-4">
              <img
                src={profile.profile_picture}
                alt="Profile"
                className="w-16 h-16 rounded-full"
              />
            </div>
          )}
        </div>
      )}

      {errors.general && (
        <div className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded">
          {errors.general}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label htmlFor="full_name" className="block text-sm font-medium text-gray-700 mb-1">
            Full Name
          </label>
          <input
            type="text"
            id="full_name"
            name="full_name"
            value={formData.full_name}
            onChange={handleInputChange}
            className={`w-full px-3 py-2 border rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
              errors.full_name ? 'border-red-500' : 'border-gray-300'
            }`}
            disabled={isLoading}
          />
          {errors.full_name && (
            <p className="text-red-500 text-sm mt-1">{errors.full_name}</p>
          )}
        </div>

        <div>
          <h3 className="text-lg font-medium text-gray-900 mb-4">Preferences</h3>

          <div className="space-y-4">
            <div>
              <label htmlFor="preferences.theme" className="block text-sm font-medium text-gray-700 mb-1">
                Theme
              </label>
              <select
                id="preferences.theme"
                name="preferences.theme"
                value={formData.preferences.theme}
                onChange={handleInputChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                disabled={isLoading}
              >
                <option value="light">Light</option>
                <option value="dark">Dark</option>
                <option value="auto">Auto</option>
              </select>
            </div>

            <div className="flex items-center">
              <input
                type="checkbox"
                id="preferences.notifications"
                name="preferences.notifications"
                checked={formData.preferences.notifications}
                onChange={handleCheckboxChange}
                className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                disabled={isLoading}
              />
              <label htmlFor="preferences.notifications" className="ml-2 block text-sm text-gray-700">
                Enable push notifications
              </label>
            </div>

            <div className="flex items-center">
              <input
                type="checkbox"
                id="preferences.marketing_emails"
                name="preferences.marketing_emails"
                checked={formData.preferences.marketing_emails}
                onChange={handleCheckboxChange}
                className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                disabled={isLoading}
              />
              <label htmlFor="preferences.marketing_emails" className="ml-2 block text-sm text-gray-700">
                Receive marketing emails
              </label>
            </div>
          </div>
        </div>

        <div className="flex space-x-4">
          <button
            type="submit"
            disabled={isLoading}
            className="flex-1 bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isLoading ? 'Updating...' : 'Update Profile'}
          </button>

          <button
            type="button"
            onClick={fetchProfile}
            disabled={isLoading || isFetching}
            className="px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Reset
          </button>
        </div>
      </form>
    </div>
  );
}