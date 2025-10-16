/**
 * Login page component.
 *
 * Provides user authentication via email/password and Google OAuth.
 *
 * @module app/login/page
 */

'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Wine } from 'lucide-react';
import GoogleSignInButton from '@/components/auth/GoogleSignInButton';
import OAuthDiagnostics from '@/components/auth/OAuthDiagnostics';
import { useAuth } from '@/hooks/useAuth';

/**
 * Login page component
 *
 * @returns {JSX.Element} Rendered login page
 */
export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      await login(email, password);
      router.push('/account');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-wine-deep via-background to-wine-deep/20 flex items-center justify-center px-4 py-8">
      <div className="w-full max-w-md">
        {/* Logo and Title */}
        <div className="text-center mb-8">
          <Link href="/" className="inline-flex items-center gap-2 group mb-4">
            <Wine className="w-10 h-10 text-wine-rose group-hover:text-wine-periwinkle transition-colors" />
            <span className="font-display text-3xl font-semibold tracking-tight bg-gradient-to-r from-wine-rose via-wine-periwinkle to-wine-cyan bg-clip-text text-transparent">
              A Fine Wine Dynasty
            </span>
          </Link>
          <h1 className="text-2xl font-bold text-foreground mt-4">
            Sign In
          </h1>
          <p className="text-muted-foreground mt-2">
            Sign in to access your fantasy baseball dynasty
          </p>
        </div>

        {/* Login Card */}
        <div className="bg-card border border-border rounded-lg shadow-xl p-8">
          {error && (
            <div className="mb-6 p-4 bg-destructive/10 border border-destructive/20 text-destructive rounded-md text-sm">
              {error}
            </div>
          )}

          {/* Google Sign In */}
          <div className="mb-6">
            <GoogleSignInButton className="w-full" />
          </div>

          {/* Divider */}
          <div className="relative mb-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-border"></div>
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="px-4 bg-card text-muted-foreground">
                Or continue with email
              </span>
            </div>
          </div>

          {/* Email/Password Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label
                htmlFor="email"
                className="block text-sm font-medium text-foreground mb-2"
              >
                Email Address
              </label>
              <input
                type="email"
                id="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-2.5 bg-background border border-border rounded-md focus:outline-none focus:ring-2 focus:ring-wine-periwinkle focus:border-transparent transition-all"
                placeholder="you@example.com"
                required
                disabled={isLoading}
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <label
                  htmlFor="password"
                  className="block text-sm font-medium text-foreground"
                >
                  Password
                </label>
                <Link
                  href="/forgot-password"
                  className="text-sm text-wine-periwinkle hover:text-wine-rose transition-colors"
                >
                  Forgot password?
                </Link>
              </div>
              <input
                type="password"
                id="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-2.5 bg-background border border-border rounded-md focus:outline-none focus:ring-2 focus:ring-wine-periwinkle focus:border-transparent transition-all"
                placeholder="••••••••"
                required
                disabled={isLoading}
              />
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full bg-gradient-to-r from-wine-rose to-wine-periwinkle hover:from-wine-deep hover:to-wine-rose text-white font-medium py-2.5 px-4 rounded-md shadow-md hover:shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? 'Signing in...' : 'Sign In'}
            </button>
          </form>

          {/* Sign Up Link */}
          <div className="mt-6 text-center">
            <p className="text-sm text-muted-foreground">
              Don't have an account?{' '}
              <Link
                href="/register"
                className="text-wine-periwinkle hover:text-wine-rose font-medium transition-colors"
              >
                Create one here
              </Link>
            </p>
          </div>
        </div>

        {/* Back to Home */}
        <div className="mt-6 text-center">
          <Link
            href="/"
            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            ← Back to Home
          </Link>
        </div>
      </div>

      {/* OAuth Diagnostics - Only shows in development */}
      <OAuthDiagnostics />
    </div>
  );
}
