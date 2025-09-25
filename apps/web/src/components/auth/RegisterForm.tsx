'use client';

import React, { useState, useRef, useEffect } from 'react';
import { AuthAPI } from '@/lib/auth/api';
import { GoogleOAuth } from '@/lib/auth/google';

interface RegisterFormProps {
  onSuccess?: (userId: number) => void;
  onError?: (error: string) => void;
  switchToLogin?: () => void;
}

interface FormData {
  email: string;
  password: string;
  confirmPassword: string;
  full_name: string;
}

interface FormErrors {
  email?: string;
  password?: string;
  confirmPassword?: string;
  full_name?: string;
  general?: string;
}

export function RegisterForm({ onSuccess, onError, switchToLogin }: RegisterFormProps) {
  const [formData, setFormData] = useState<FormData>({
    email: '',
    password: '',
    confirmPassword: '',
    full_name: '',
  });
  const [errors, setErrors] = useState<FormErrors>({});
  const [isLoading, setIsLoading] = useState(false);
  const googleButtonRef = useRef<HTMLDivElement>(null);

  const googleClientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
  const googleRedirectUri = process.env.NEXT_PUBLIC_GOOGLE_REDIRECT_URI;

  useEffect(() => {
    // Initialize Google OAuth when component mounts
    if (googleClientId && googleRedirectUri && googleButtonRef.current) {
      const googleOAuth = GoogleOAuth.getInstance({
        clientId: googleClientId,
        redirectUri: googleRedirectUri,
      });

      googleOAuth.initialize().then(() => {
        if (googleButtonRef.current) {
          googleOAuth.renderSignInButton(googleButtonRef.current, {
            text: 'signup_with',
            theme: 'outline',
            size: 'large',
            width: 320,
          });
        }
      }).catch(console.error);
    }
  }, [googleClientId, googleRedirectUri]);

  const validateForm = (): boolean => {
    const newErrors: FormErrors = {};

    // Email validation
    if (!formData.email) {
      newErrors.email = 'Email is required';
    } else if (!/\S+@\S+\.\S+/.test(formData.email)) {
      newErrors.email = 'Email format is invalid';
    }

    // Full name validation
    if (!formData.full_name.trim()) {
      newErrors.full_name = 'Full name is required';
    } else if (formData.full_name.trim().length < 2) {
      newErrors.full_name = 'Full name must be at least 2 characters';
    }

    // Password validation
    if (!formData.password) {
      newErrors.password = 'Password is required';
    } else if (formData.password.length < 8) {
      newErrors.password = 'Password must be at least 8 characters';
    } else if (!/(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{};':\",./<>?])/.test(formData.password)) {
      newErrors.password = 'Password must contain uppercase, lowercase, number, and special character';
    }

    // Confirm password validation
    if (!formData.confirmPassword) {
      newErrors.confirmPassword = 'Please confirm your password';
    } else if (formData.password !== formData.confirmPassword) {
      newErrors.confirmPassword = 'Passwords do not match';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));

    // Clear specific field error when user starts typing
    if (errors[name as keyof FormErrors]) {
      setErrors(prev => ({ ...prev, [name]: undefined }));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    setIsLoading(true);

    try {
      const response = await AuthAPI.register({
        email: formData.email,
        password: formData.password,
        full_name: formData.full_name,
      });

      onSuccess?.(response.user_id);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Registration failed';
      setErrors({ general: errorMessage });
      onError?.(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleSuccess = async () => {
    if (!googleClientId || !googleRedirectUri) return;

    try {
      const googleOAuth = GoogleOAuth.getInstance();
      const response = await googleOAuth.signIn();

      const authResponse = await AuthAPI.googleLogin({
        code: response.code,
        state: response.state,
      });

      onSuccess?.(authResponse.user_id || 0);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Google registration failed';
      setErrors({ general: errorMessage });
      onError?.(errorMessage);
    }
  };

  return (
    <div className="max-w-md mx-auto bg-white p-8 border border-gray-300 rounded-lg shadow-lg">
      <h2 className="text-2xl font-bold text-gray-900 mb-6 text-center">
        Create Your Account
      </h2>

      {errors.general && (
        <div className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded">
          {errors.general}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
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
          <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
            Email Address
          </label>
          <input
            type="email"
            id="email"
            name="email"
            value={formData.email}
            onChange={handleInputChange}
            className={`w-full px-3 py-2 border rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
              errors.email ? 'border-red-500' : 'border-gray-300'
            }`}
            disabled={isLoading}
          />
          {errors.email && (
            <p className="text-red-500 text-sm mt-1">{errors.email}</p>
          )}
        </div>

        <div>
          <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
            Password
          </label>
          <input
            type="password"
            id="password"
            name="password"
            value={formData.password}
            onChange={handleInputChange}
            className={`w-full px-3 py-2 border rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
              errors.password ? 'border-red-500' : 'border-gray-300'
            }`}
            disabled={isLoading}
          />
          {errors.password && (
            <p className="text-red-500 text-sm mt-1">{errors.password}</p>
          )}
        </div>

        <div>
          <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700 mb-1">
            Confirm Password
          </label>
          <input
            type="password"
            id="confirmPassword"
            name="confirmPassword"
            value={formData.confirmPassword}
            onChange={handleInputChange}
            className={`w-full px-3 py-2 border rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
              errors.confirmPassword ? 'border-red-500' : 'border-gray-300'
            }`}
            disabled={isLoading}
          />
          {errors.confirmPassword && (
            <p className="text-red-500 text-sm mt-1">{errors.confirmPassword}</p>
          )}
        </div>

        <button
          type="submit"
          disabled={isLoading}
          className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isLoading ? 'Creating Account...' : 'Create Account'}
        </button>
      </form>

      {googleClientId && (
        <>
          <div className="mt-6 flex items-center">
            <div className="flex-1 border-t border-gray-300"></div>
            <div className="px-4 text-gray-500 text-sm">or</div>
            <div className="flex-1 border-t border-gray-300"></div>
          </div>

          <div className="mt-6 flex justify-center">
            <div ref={googleButtonRef} onClick={handleGoogleSuccess} />
          </div>
        </>
      )}

      <p className="mt-6 text-center text-sm text-gray-600">
        Already have an account?{' '}
        <button
          type="button"
          onClick={switchToLogin}
          className="text-blue-600 hover:text-blue-500 font-medium"
        >
          Sign in here
        </button>
      </p>
    </div>
  );
}