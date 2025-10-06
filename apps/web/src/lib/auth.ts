/**
 * Authentication utilities for Google OAuth and JWT token management
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || '';

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface User {
  id: number;
  email: string;
  full_name: string;
  profile_picture?: string;
  subscription_tier: string;
}

/**
 * Get Google OAuth authorization URL
 */
export function getGoogleAuthUrl(): string {
  const redirectUri = `${window.location.origin}/auth/callback`;
  const scope = 'openid email profile';
  const state = generateRandomState();

  // Store state for verification
  if (typeof window !== 'undefined') {
    sessionStorage.setItem('oauth_state', state);
  }

  // Debug: Log client ID status
  if (!GOOGLE_CLIENT_ID) {
    console.error('❌ NEXT_PUBLIC_GOOGLE_CLIENT_ID is not set! Check your .env.local file and restart your dev server.');
    throw new Error('Google OAuth is not configured. Please set NEXT_PUBLIC_GOOGLE_CLIENT_ID in your .env.local file and restart the dev server.');
  }

  console.log('✅ Google Client ID configured:', GOOGLE_CLIENT_ID.substring(0, 15) + '...');

  const params = new URLSearchParams({
    client_id: GOOGLE_CLIENT_ID,
    redirect_uri: redirectUri,
    response_type: 'code',
    scope,
    state,
    access_type: 'offline',
    prompt: 'consent'
  });

  return `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`;
}

/**
 * Generate random state for CSRF protection
 */
function generateRandomState(): string {
  const array = new Uint8Array(32);
  crypto.getRandomValues(array);
  return Array.from(array, byte => byte.toString(16).padStart(2, '0')).join('');
}

/**
 * Verify OAuth state parameter
 */
export function verifyOAuthState(state: string): boolean {
  if (typeof window === 'undefined') return false;
  const storedState = sessionStorage.getItem('oauth_state');
  sessionStorage.removeItem('oauth_state');
  return state === storedState;
}

/**
 * Exchange Google authorization code for tokens
 */
export async function exchangeGoogleCode(code: string, state: string): Promise<AuthTokens> {
  const response = await fetch(`${API_URL}/api/v1/auth/google/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ code, state }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to authenticate with Google');
  }

  return response.json();
}

/**
 * Store auth tokens securely
 */
export function storeTokens(tokens: AuthTokens): void {
  if (typeof window === 'undefined') return;

  // Store in localStorage (consider httpOnly cookies for production)
  localStorage.setItem('access_token', tokens.access_token);
  localStorage.setItem('refresh_token', tokens.refresh_token);
  localStorage.setItem('token_expiry', String(Date.now() + tokens.expires_in * 1000));
}

/**
 * Get stored access token
 */
export function getAccessToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('access_token');
}

/**
 * Get stored refresh token
 */
export function getRefreshToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('refresh_token');
}

/**
 * Check if access token is expired
 */
export function isTokenExpired(): boolean {
  if (typeof window === 'undefined') return true;

  const expiry = localStorage.getItem('token_expiry');
  if (!expiry) return true;

  return Date.now() >= parseInt(expiry);
}

/**
 * Refresh access token using refresh token
 */
export async function refreshAccessToken(): Promise<AuthTokens | null> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;

  try {
    const response = await fetch(`${API_URL}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!response.ok) {
      clearTokens();
      return null;
    }

    const tokens = await response.json();
    storeTokens(tokens);
    return tokens;
  } catch (error) {
    clearTokens();
    return null;
  }
}

/**
 * Clear all stored tokens
 */
export function clearTokens(): void {
  if (typeof window === 'undefined') return;

  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('token_expiry');
}

/**
 * Check if user is authenticated
 */
export function isAuthenticated(): boolean {
  const token = getAccessToken();
  if (!token) return false;

  if (isTokenExpired()) {
    // Try to refresh token
    refreshAccessToken();
    return false;
  }

  return true;
}

/**
 * Logout user
 */
export async function logout(): Promise<void> {
  const token = getAccessToken();

  if (token) {
    try {
      await fetch(`${API_URL}/api/v1/auth/logout`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });
    } catch (error) {
      console.error('Logout error:', error);
    }
  }

  clearTokens();
}

/**
 * Get current user info from token
 */
export async function getCurrentUser(): Promise<User | null> {
  const token = getAccessToken();
  if (!token) return null;

  try {
    const response = await fetch(`${API_URL}/api/v1/users/me`, {
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      if (response.status === 401) {
        // Token expired, try to refresh
        const newTokens = await refreshAccessToken();
        if (newTokens) {
          return getCurrentUser(); // Retry with new token
        }
      }
      return null;
    }

    return response.json();
  } catch (error) {
    console.error('Get user error:', error);
    return null;
  }
}
