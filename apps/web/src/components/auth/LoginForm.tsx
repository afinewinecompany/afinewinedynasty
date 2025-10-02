'use client';

import React, { useState, useRef, useEffect } from 'react';
import { AuthAPI } from '@/lib/auth/api';
import { GoogleOAuth } from '@/lib/auth/google';

interface LoginFormProps {
  onSuccess?: () => void;
  onError?: (error: string) => void;
  switchToRegister?: () => void;
  onForgotPassword?: () => void;
}

interface FormData {
  email: string;
  password: string;
}

interface FormErrors {
  email?: string;
  password?: string;
  general?: string;
}

export function LoginForm({
  onSuccess,
  onError,
  switchToRegister,
  onForgotPassword,
}: LoginFormProps) {
  const [formData, setFormData] = useState<FormData>({
    email: '',
    password: '',
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

      googleOAuth
        .initialize()
        .then(() => {
          if (googleButtonRef.current) {
            googleOAuth.renderSignInButton(googleButtonRef.current, {
              text: 'signin_with',
              theme: 'outline',
              size: 'large',
              width: 320,
            });
          }
        })
        .catch(console.error);
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

    // Password validation
    if (!formData.password) {
      newErrors.password = 'Password is required';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));

    // Clear specific field error when user starts typing
    if (errors[name as keyof FormErrors]) {
      setErrors((prev) => ({ ...prev, [name]: undefined }));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    setIsLoading(true);

    try {
      await AuthAPI.login({
        email: formData.email,
        password: formData.password,
      });

      onSuccess?.();
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : 'Login failed';
      setErrors({ general: errorMessage });
      onError?.(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleSuccess = async () => {
    if (!googleClientId || !googleRedirectUri) return;

    try {
      setIsLoading(true);
      const googleOAuth = GoogleOAuth.getInstance();
      const response = await googleOAuth.signIn();

      await AuthAPI.googleLogin({
        code: response.code,
        state: response.state,
      });

      onSuccess?.();
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : 'Google login failed';
      setErrors({ general: errorMessage });
      onError?.(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const handleForgotPassword = async () => {
    if (!formData.email) {
      setErrors({ email: 'Please enter your email address first' });
      return;
    }

    try {
      setIsLoading(true);
      await AuthAPI.requestPasswordReset(formData.email);
      alert('Password reset link sent to your email address');
      onForgotPassword?.();
    } catch (error) {
      const errorMessage =
        error instanceof Error
          ? error.message
          : 'Password reset request failed';
      setErrors({ general: errorMessage });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="max-w-md mx-auto bg-white p-8 border border-gray-300 rounded-lg shadow-lg">
      <h2 className="text-2xl font-bold text-gray-900 mb-6 text-center">
        Sign In to Your Account
      </h2>

      {errors.general && (
        <div className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded">
          {errors.general}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label
            htmlFor="email"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
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
          <label
            htmlFor="password"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
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

        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={handleForgotPassword}
            className="text-sm text-blue-600 hover:text-blue-500"
            disabled={isLoading}
          >
            Forgot your password?
          </button>
        </div>

        <button
          type="submit"
          disabled={isLoading}
          className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isLoading ? 'Signing In...' : 'Sign In'}
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
        Don&apos;t have an account?{' '}
        <button
          type="button"
          onClick={switchToRegister}
          className="text-blue-600 hover:text-blue-500 font-medium"
        >
          Create one here
        </button>
      </p>
    </div>
  );
}
