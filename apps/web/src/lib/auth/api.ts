// Authentication API client utilities

interface LoginCredentials {
  email: string;
  password: string;
}

interface RegisterCredentials {
  email: string;
  password: string;
  full_name: string;
}

interface GoogleOAuthRequest {
  code: string;
  state?: string;
}

interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user_id?: number;
  is_new_user?: boolean;
}

interface UserProfile {
  id: number;
  email: string;
  full_name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  google_id?: string;
  profile_picture?: string;
  preferences?: Record<string, any>;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class AuthAPI {
  private static getAuthHeaders(): HeadersInit {
    const token = localStorage.getItem('access_token');
    return {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
    };
  }

  static async login(credentials: LoginCredentials): Promise<AuthResponse> {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(credentials),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Login failed');
    }

    const data = await response.json();

    // Store tokens securely
    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);

    return data;
  }

  static async register(
    credentials: RegisterCredentials
  ): Promise<{ message: string; user_id: number }> {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(credentials),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Registration failed');
    }

    return response.json();
  }

  static async googleLogin(
    oauthRequest: GoogleOAuthRequest
  ): Promise<AuthResponse> {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/google/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(oauthRequest),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Google login failed');
    }

    const data = await response.json();

    // Store tokens securely
    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);

    return data;
  }

  static async refreshToken(): Promise<AuthResponse> {
    const refreshToken = localStorage.getItem('refresh_token');
    if (!refreshToken) {
      throw new Error('No refresh token available');
    }

    const response = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!response.ok) {
      // If refresh fails, clear tokens and redirect to login
      this.logout();
      throw new Error('Token refresh failed');
    }

    const data = await response.json();

    // Update stored tokens
    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);

    return data;
  }

  static async logout(): Promise<void> {
    try {
      await fetch(`${API_BASE_URL}/api/v1/auth/logout`, {
        method: 'POST',
        headers: this.getAuthHeaders(),
      });
    } catch (error) {
      console.error('Logout request failed:', error);
    } finally {
      // Always clear local tokens
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
    }
  }

  static async getUserProfile(): Promise<UserProfile> {
    const response = await fetch(`${API_BASE_URL}/api/v1/users/profile`, {
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      if (response.status === 401) {
        // Try to refresh token
        await this.refreshToken();
        // Retry the request
        const retryResponse = await fetch(
          `${API_BASE_URL}/api/v1/users/profile`,
          {
            headers: this.getAuthHeaders(),
          }
        );
        if (!retryResponse.ok) {
          throw new Error('Failed to get user profile');
        }
        return retryResponse.json();
      }
      throw new Error('Failed to get user profile');
    }

    return response.json();
  }

  static async updateProfile(data: {
    full_name?: string;
    preferences?: Record<string, any>;
  }): Promise<UserProfile> {
    const response = await fetch(`${API_BASE_URL}/api/v1/users/profile`, {
      method: 'PUT',
      headers: this.getAuthHeaders(),
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Profile update failed');
    }

    return response.json();
  }

  static async requestPasswordReset(email: string): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/password-reset`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Password reset request failed');
    }
  }

  static isAuthenticated(): boolean {
    return !!localStorage.getItem('access_token');
  }
}

export { AuthAPI, type AuthResponse, type UserProfile };
