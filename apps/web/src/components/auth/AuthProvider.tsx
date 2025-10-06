'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';
import { getCurrentUser, logout as authLogout, isAuthenticated } from '@/lib/auth';

interface User {
  id: number;
  email: string;
  full_name: string;
  profile_picture?: string;
  subscription_tier: string;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: () => void;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const loadUser = async () => {
    try {
      if (isAuthenticated()) {
        const userData = await getCurrentUser();
        setUser(userData);
      } else {
        setUser(null);
      }
    } catch (error) {
      console.error('Failed to load user:', error);
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUser();
  }, []);

  const login = () => {
    // Store current path for redirect after login
    if (typeof window !== 'undefined') {
      sessionStorage.setItem('auth_redirect', window.location.pathname);
    }
  };

  const logout = async () => {
    await authLogout();
    setUser(null);
    if (typeof window !== 'undefined') {
      window.location.href = '/';
    }
  };

  const refreshUser = async () => {
    await loadUser();
  };

  const value: AuthContextType = {
    user,
    loading,
    isAuthenticated: !!user,
    login,
    logout,
    refreshUser,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
