/**
 * Fantrax Username/Password Login Modal
 *
 * DEPRECATED: This method does not work due to Cloudflare protection.
 * Redirects users to cookie-based authentication instead.
 *
 * @component FantraxLoginModal
 * @since 1.0.0
 * @deprecated Use FantraxCookieAuthModal instead
 */

'use client';

import React, { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, CheckCircle2, AlertCircle, ShieldCheck, XCircle } from 'lucide-react';

/**
 * Component props
 */
interface FantraxLoginModalProps {
  /** Whether modal is open */
  isOpen: boolean;
  /** Callback when modal closes */
  onClose: () => void;
  /** Callback on successful authentication */
  onSuccess: () => void;
}

/**
 * Fantrax username/password login modal
 *
 * @param {FantraxLoginModalProps} props - Component props
 * @returns {JSX.Element} Rendered login modal
 *
 * @example
 * ```tsx
 * <FantraxLoginModal
 *   isOpen={showModal}
 *   onClose={() => setShowModal(false)}
 *   onSuccess={() => console.log('Connected!')}
 * />
 * ```
 *
 * @since 1.0.0
 */
export function FantraxLoginModal({
  isOpen,
  onClose,
  onSuccess,
}: FantraxLoginModalProps): JSX.Element {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  /**
   * Handle form submission
   */
  const handleSubmit = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      const token = localStorage.getItem('access_token');
      if (!token) {
        throw new Error('Not authenticated. Please log in again.');
      }

      const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(`${API_BASE_URL}/api/v1/fantrax/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ email, password }),
      });

      const data = await response.json();

      if (response.ok && data.success) {
        // Success!
        setSuccess(true);
        setEmail('');
        setPassword('');

        // Wait a moment to show success message
        setTimeout(() => {
          onSuccess();
          handleClose();
        }, 1500);
      } else {
        // Handle error
        const errorMessage = data.detail || data.error || 'Invalid credentials';
        setError(errorMessage);
      }
    } catch (err: any) {
      console.error('Fantrax login error:', err);
      setError(err.message || 'Failed to connect to Fantrax. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Close modal and reset state
   */
  const handleClose = (): void => {
    if (!isLoading) {
      setEmail('');
      setPassword('');
      setError(null);
      setSuccess(false);
      onClose();
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Connect to Fantrax</DialogTitle>
          <DialogDescription>
            Username/password authentication is no longer available
          </DialogDescription>
        </DialogHeader>

        {/* Deprecation Notice */}
        <div className="py-6 flex flex-col items-center gap-4">
          <XCircle className="h-16 w-16 text-red-600" />
          <div className="text-center space-y-3">
            <p className="font-semibold text-lg">Method Not Available</p>
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                Username/password authentication no longer works due to Cloudflare bot protection.
                Please use cookie-based authentication instead.
              </AlertDescription>
            </Alert>
            <p className="text-sm text-muted-foreground">
              Cookie-based authentication is more reliable and secure.
            </p>
          </div>
          <Button onClick={handleClose} className="w-full">
            Close
          </Button>
        </div>

        {/* Legacy form hidden - keeping for reference but not functional */}
        {false && success ? (
          // Success State
          <div className="py-6 flex flex-col items-center gap-4">
            <CheckCircle2 className="h-16 w-16 text-green-600" />
            <div className="text-center">
              <p className="font-semibold text-lg">Successfully Connected!</p>
              <p className="text-sm text-muted-foreground mt-1">
                Loading your Fantrax leagues...
              </p>
            </div>
          </div>
        ) : false && (
          // Login Form
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Email Field */}
            <div className="space-y-2">
              <Label htmlFor="fantrax-email">Fantrax Email</Label>
              <Input
                id="fantrax-email"
                type="email"
                placeholder="your@email.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={isLoading}
                required
                autoComplete="email"
              />
            </div>

            {/* Password Field */}
            <div className="space-y-2">
              <Label htmlFor="fantrax-password">Fantrax Password</Label>
              <Input
                id="fantrax-password"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isLoading}
                required
                autoComplete="current-password"
              />
            </div>

            {/* Error Alert */}
            {error && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {/* Security Notice */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
              <div className="flex items-start gap-2">
                <ShieldCheck className="h-4 w-4 text-blue-600 mt-0.5 flex-shrink-0" />
                <div className="text-xs text-blue-900">
                  <p className="font-semibold mb-1">Your credentials are secure</p>
                  <ul className="space-y-0.5 list-disc list-inside text-blue-800">
                    <li>Passwords are never stored</li>
                    <li>Only encrypted session cookies are saved</li>
                    <li>Connection is protected with HTTPS</li>
                  </ul>
                </div>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex gap-2 pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={handleClose}
                disabled={isLoading}
                className="flex-1"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={isLoading || !email || !password}
                className="flex-1"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Connecting...
                  </>
                ) : (
                  'Connect'
                )}
              </Button>
            </div>

            {/* Help Text */}
            <p className="text-xs text-center text-muted-foreground pt-2">
              Don't have a Fantrax account?{' '}
              <a
                href="https://www.fantrax.com/signup"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline"
              >
                Sign up here
              </a>
            </p>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
