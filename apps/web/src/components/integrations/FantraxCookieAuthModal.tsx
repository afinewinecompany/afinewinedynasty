/**
 * Fantrax Cookie-Based Authentication Modal
 *
 * Allows users to authenticate by pasting cookies exported from their browser.
 * This method bypasses Cloudflare protection and works reliably.
 *
 * @component FantraxCookieAuthModal
 * @since 1.0.0
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
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Loader2,
  CheckCircle2,
  AlertCircle,
  ShieldCheck,
  ExternalLink,
  Copy,
  Info
} from 'lucide-react';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs';

/**
 * Component props
 */
interface FantraxCookieAuthModalProps {
  /** Whether modal is open */
  isOpen: boolean;
  /** Callback when modal closes */
  onClose: () => void;
  /** Callback on successful authentication */
  onSuccess: () => void;
}

/**
 * Fantrax cookie-based authentication modal
 *
 * @param {FantraxCookieAuthModalProps} props - Component props
 * @returns {JSX.Element} Rendered authentication modal
 *
 * @example
 * ```tsx
 * <FantraxCookieAuthModal
 *   isOpen={showModal}
 *   onClose={() => setShowModal(false)}
 *   onSuccess={() => console.log('Connected!')}
 * />
 * ```
 *
 * @since 1.0.0
 */
export function FantraxCookieAuthModal({
  isOpen,
  onClose,
  onSuccess,
}: FantraxCookieAuthModalProps): JSX.Element {
  const [cookiesJson, setCookiesJson] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  /**
   * Validate JSON format
   */
  const validateCookies = (json: string): boolean => {
    try {
      const parsed = JSON.parse(json);
      if (!Array.isArray(parsed)) {
        setError('Cookies must be a JSON array');
        return false;
      }
      if (parsed.length === 0) {
        setError('No cookies found in the JSON');
        return false;
      }
      return true;
    } catch (e) {
      setError('Invalid JSON format. Please check your cookies.');
      return false;
    }
  };

  /**
   * Handle form submission
   */
  const handleSubmit = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault();
    setError(null);

    // Validate cookies
    if (!validateCookies(cookiesJson)) {
      return;
    }

    setIsLoading(true);

    try {
      const token = localStorage.getItem('access_token');
      if (!token) {
        throw new Error('Not authenticated. Please log in again.');
      }

      const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(`${API_BASE_URL}/api/v1/fantrax/auth/cookie-auth`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ cookies_json: cookiesJson }),
      });

      const data = await response.json();

      if (response.ok && data.success) {
        // Success!
        setSuccess(true);
        setCookiesJson('');

        // Wait a moment to show success message
        setTimeout(() => {
          onSuccess();
          handleClose();
        }, 1500);
      } else {
        // Handle error
        const errorMessage = data.detail || data.error || 'Failed to store cookies';
        setError(errorMessage);
      }
    } catch (err: any) {
      console.error('Fantrax cookie auth error:', err);
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
      setCookiesJson('');
      setError(null);
      setSuccess(false);
      onClose();
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Connect to Fantrax</DialogTitle>
          <DialogDescription>
            Authenticate using cookies exported from your browser
          </DialogDescription>
        </DialogHeader>

        {success ? (
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
        ) : (
          <div className="space-y-4">
            {/* Instructions Tabs */}
            <Tabs defaultValue="chrome" className="w-full">
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="chrome">Chrome</TabsTrigger>
                <TabsTrigger value="firefox">Firefox</TabsTrigger>
              </TabsList>

              {/* Chrome Instructions */}
              <TabsContent value="chrome" className="space-y-3">
                <Alert>
                  <Info className="h-4 w-4" />
                  <AlertDescription>
                    <p className="font-semibold mb-2">How to export cookies in Chrome:</p>
                    <ol className="list-decimal list-inside space-y-1 text-sm">
                      <li>
                        Install{' '}
                        <a
                          href="https://chrome.google.com/webstore/detail/editthiscookie/fngmhnnpilhplaeedifhccceomclgfbg"
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:underline inline-flex items-center gap-1"
                        >
                          EditThisCookie extension
                          <ExternalLink className="h-3 w-3" />
                        </a>
                      </li>
                      <li>Go to <strong>fantrax.com</strong> and log in</li>
                      <li>Click the EditThisCookie extension icon</li>
                      <li>Click the <strong>Export</strong> button (looks like a download icon)</li>
                      <li>Paste the copied JSON below</li>
                    </ol>
                  </AlertDescription>
                </Alert>
              </TabsContent>

              {/* Firefox Instructions */}
              <TabsContent value="firefox" className="space-y-3">
                <Alert>
                  <Info className="h-4 w-4" />
                  <AlertDescription>
                    <p className="font-semibold mb-2">How to export cookies in Firefox:</p>
                    <ol className="list-decimal list-inside space-y-1 text-sm">
                      <li>
                        Install{' '}
                        <a
                          href="https://addons.mozilla.org/en-US/firefox/addon/cookie-editor/"
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:underline inline-flex items-center gap-1"
                        >
                          Cookie-Editor extension
                          <ExternalLink className="h-3 w-3" />
                        </a>
                      </li>
                      <li>Go to <strong>fantrax.com</strong> and log in</li>
                      <li>Click the Cookie-Editor extension icon</li>
                      <li>Click <strong>Export</strong> at the bottom</li>
                      <li>Paste the copied JSON below</li>
                    </ol>
                  </AlertDescription>
                </Alert>
              </TabsContent>
            </Tabs>

            {/* Cookie Input Form */}
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="cookies-json">Fantrax Cookies (JSON)</Label>
                <Textarea
                  id="cookies-json"
                  placeholder='[{"name":"sessionid","value":"...","domain":".fantrax.com"}]'
                  value={cookiesJson}
                  onChange={(e) => {
                    setCookiesJson(e.target.value);
                    setError(null);
                  }}
                  disabled={isLoading}
                  required
                  className="font-mono text-xs min-h-[120px]"
                />
                <p className="text-xs text-muted-foreground">
                  Paste the JSON array of cookies from your browser extension
                </p>
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
                    <p className="font-semibold mb-1">Your cookies are secure</p>
                    <ul className="space-y-0.5 list-disc list-inside text-blue-800">
                      <li>Cookies are encrypted with AES-256 before storage</li>
                      <li>Cookies expire after 30 days (Fantrax default)</li>
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
                  disabled={isLoading || !cookiesJson}
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
            </form>

            {/* Why Cookie Auth */}
            <Alert className="bg-amber-50 border-amber-200">
              <AlertCircle className="h-4 w-4 text-amber-600" />
              <AlertDescription className="text-xs text-amber-900">
                <p className="font-semibold mb-1">Why cookie-based authentication?</p>
                <p>
                  Fantrax uses Cloudflare protection that blocks automated logins.
                  Cookie-based authentication is the most reliable method for integrating
                  your Fantrax account.
                </p>
              </AlertDescription>
            </Alert>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
