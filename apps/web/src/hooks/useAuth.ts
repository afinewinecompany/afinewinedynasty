/**
 * @fileoverview Authentication hook for managing user authentication state
 *
 * This hook provides access to the current user's authentication state,
 * subscription tier, and authentication actions (login, logout, etc.).
 *
 * @module useAuth
 * @version 1.0.0
 * @since 1.0.0
 */

'use client';

import { useState, useEffect, useCallback } from 'react';
import { AuthAPI, type UserProfile } from '@/lib/auth/api';
import { useRouter } from 'next/navigation';

interface User extends UserProfile {
  subscriptionTier: 'free' | 'premium';
}

interface UseAuthReturn {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

/**
 * Custom hook for managing user authentication state
 *
 * @hook useAuth
 * @returns {UseAuthReturn} Authentication state and control functions
 *
 * @example
 * ```tsx
 * const { user, isAuthenticated, login, logout } = useAuth();
 *
 * if (!isAuthenticated) {
 *   return <LoginForm onLogin={login} />;
 * }
 *
 * return <Dashboard user={user} onLogout={logout} />;
 * ```
 */
export function useAuth(): UseAuthReturn {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  /**
   * Fetches the current user profile and subscription data
   */
  const fetchUser = useCallback(async (): Promise<void> => {
    try {
      if (!AuthAPI.isAuthenticated()) {
        setUser(null);
        setIsLoading(false);
        return;
      }

      const profile = await AuthAPI.getUserProfile();

      // Fetch actual subscription tier from API
      let subscriptionTier: 'free' | 'premium' = 'free';
      try {
        const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
        const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;

        if (token) {
          const response = await fetch(`${API_BASE_URL}/api/v1/subscriptions/status`, {
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
          });

          if (response.ok) {
            const subscriptionData = await response.json();
            // Map subscription tier from API response
            subscriptionTier = subscriptionData.tier === 'premium' ? 'premium' : 'free';
          }
        }
      } catch (subscriptionError) {
        console.warn('Failed to fetch subscription status, defaulting to free:', subscriptionError);
        // Continue with default 'free' tier if subscription fetch fails
      }

      setUser({
        ...profile,
        subscriptionTier,
      });
    } catch (error) {
      console.error('Failed to fetch user profile:', error);
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * Logs in a user with email and password
   *
   * @param email - User's email address
   * @param password - User's password
   * @throws {Error} When login credentials are invalid
   */
  const login = useCallback(
    async (email: string, password: string): Promise<void> => {
      setIsLoading(true);
      try {
        await AuthAPI.login({ email, password });
        await fetchUser();
        router.push('/');
      } catch (error) {
        setIsLoading(false);
        throw error;
      }
    },
    [fetchUser, router]
  );

  /**
   * Logs out the current user and redirects to login page
   */
  const logout = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    try {
      await AuthAPI.logout();
      setUser(null);
      router.push('/login');
    } catch (error) {
      console.error('Logout failed:', error);
    } finally {
      setIsLoading(false);
    }
  }, [router]);

  /**
   * Refreshes the current user's profile data
   */
  const refreshUser = useCallback(async (): Promise<void> => {
    await fetchUser();
  }, [fetchUser]);

  // Fetch user on mount
  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  return {
    user,
    isLoading,
    isAuthenticated: !!user,
    login,
    logout,
    refreshUser,
  };
}
