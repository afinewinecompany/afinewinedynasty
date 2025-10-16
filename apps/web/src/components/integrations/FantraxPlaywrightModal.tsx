/**
 * Fantrax Browser Authentication Modal
 *
 * Opens Fantrax login in user's browser, provides bookmarklet to extract cookies.
 *
 * @component FantraxPlaywrightModal
 * @since 1.2.0
 */

'use client';

import React, { useState, useEffect, useRef } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Loader2,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  ShieldCheck,
  Info,
  Copy,
  Check
} from 'lucide-react';

/**
 * Component props
 */
interface FantraxPlaywrightModalProps {
  /** Whether modal is open */
  isOpen: boolean;
  /** Callback when modal closes */
  onClose: () => void;
  /** Callback on successful authentication */
  onSuccess: () => void;
}

/**
 * Authentication state
 */
type AuthState =
  | 'instructions'
  | 'waiting'
  | 'success'
  | 'failed';

const FANTRAX_LOGIN_URL = 'https://www.fantrax.com/login';

/**
 * Fantrax browser authentication modal
 */
export function FantraxPlaywrightModal({
  isOpen,
  onClose,
  onSuccess,
}: FantraxPlaywrightModalProps): JSX.Element {
  const [state, setState] = useState<AuthState>('instructions');
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const loginWindowRef = useRef<Window | null>(null);

  /**
   * Get API base URL
   */
  const getApiUrl = () => {
    return process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  };

  /**
   * Get auth token
   */
  const getAuthToken = () => {
    return localStorage.getItem('access_token');
  };

  /**
   * Bookmarklet code that extracts cookies and sends them
   */
  const getBookmarkletCode = () => {
    const apiUrl = getApiUrl();
    const token = getAuthToken();
    const origin = window.location.origin;

    return `(async function() {
  try {
    const cookies = document.cookie.split(';').map(c => {
      const [name, ...valueParts] = c.trim().split('=');
      return {
        name: name.trim(),
        value: valueParts.join('='),
        domain: '.fantrax.com',
        path: '/',
        secure: true,
        sameSite: 'Lax'
      };
    }).filter(c => c.name && c.value);

    if (cookies.length === 0) {
      alert('No cookies found. Make sure you are logged in to Fantrax.');
      return;
    }

    // Send to opener if exists (popup mode)
    if (window.opener && !window.opener.closed) {
      window.opener.postMessage({
        type: 'FANTRAX_COOKIES',
        cookies: cookies
      }, '${origin}');
      alert('Cookies sent! You can close this window.');
    } else {
      // Direct mode - send to API
      const response = await fetch('${apiUrl}/api/v1/fantrax/auth/cookie-auth', {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer ${token}',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ cookies_json: JSON.stringify(cookies) })
      });

      const data = await response.json();

      if (response.ok && data.success) {
        alert('Success! Your Fantrax account is connected. You can close this tab.');
      } else {
        alert('Error: ' + (data.detail || 'Failed to save session'));
      }
    }
  } catch (error) {
    alert('Error: ' + error.message);
  }
})();`;
  };

  /**
   * Open Fantrax login in new window
   */
  const openLoginWindow = () => {
    try {
      const width = 1000;
      const height = 800;
      const left = (window.screen.width - width) / 2;
      const top = (window.screen.height - height) / 2;

      const loginWindow = window.open(
        FANTRAX_LOGIN_URL,
        'fantrax_login',
        `width=${width},height=${height},left=${left},top=${top},resizable=yes,scrollbars=yes,toolbar=yes,menubar=yes`
      );

      if (!loginWindow) {
        setError('Failed to open login window. Please allow popups for this site.');
        setState('failed');
        return;
      }

      loginWindowRef.current = loginWindow;
      setState('waiting');
    } catch (err: any) {
      console.error('Failed to open login window:', err);
      setError(err.message || 'Failed to open login window');
      setState('failed');
    }
  };

  /**
   * Copy bookmarklet code to clipboard
   */
  const copyBookmarkletCode = async () => {
    try {
      await navigator.clipboard.writeText(getBookmarkletCode());
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
      alert('Failed to copy to clipboard. Please copy manually.');
    }
  };

  /**
   * Handle message from login window
   */
  const handleMessage = async (event: MessageEvent) => {
    // Verify origin
    if (event.origin !== window.location.origin) return;

    if (event.data.type === 'FANTRAX_COOKIES') {
      const cookies = event.data.cookies;

      if (!cookies || cookies.length === 0) {
        setError('No cookies received. Please make sure you logged in successfully.');
        setState('failed');
        return;
      }

      // Send cookies to backend
      await sendCookiesToBackend(cookies);
    }
  };

  /**
   * Send cookies to backend for storage
   */
  const sendCookiesToBackend = async (cookies: any[]) => {
    const token = getAuthToken();
    if (!token) {
      setError('Not authenticated. Please log in again.');
      setState('failed');
      return;
    }

    try {
      const response = await fetch(`${getApiUrl()}/api/v1/fantrax/auth/cookie-auth`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          cookies_json: JSON.stringify(cookies)
        }),
      });

      const data = await response.json();

      if (response.ok && data.success) {
        setState('success');
        closeLoginWindow();

        // Wait a moment to show success message
        setTimeout(() => {
          onSuccess();
          handleClose();
        }, 1500);
      } else {
        setError(data.detail || 'Failed to save session');
        setState('failed');
      }
    } catch (err: any) {
      console.error('Failed to send cookies to backend:', err);
      setError(err.message || 'Failed to save session');
      setState('failed');
    }
  };

  /**
   * Close login window
   */
  const closeLoginWindow = () => {
    if (loginWindowRef.current && !loginWindowRef.current.closed) {
      loginWindowRef.current.close();
    }
    loginWindowRef.current = null;
  };

  /**
   * Close modal and reset state
   */
  const handleClose = () => {
    closeLoginWindow();
    setState('instructions');
    setError(null);
    setCopied(false);
    onClose();
  };

  /**
   * Listen for messages from login window
   */
  useEffect(() => {
    window.addEventListener('message', handleMessage);
    return () => {
      window.removeEventListener('message', handleMessage);
    };
  }, []);

  /**
   * Cleanup on unmount
   */
  useEffect(() => {
    return () => {
      closeLoginWindow();
    };
  }, []);

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Connect to Fantrax</DialogTitle>
          <DialogDescription>
            Log in to Fantrax and run a simple script to connect your account
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {state === 'success' ? (
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
          ) : state === 'failed' ? (
            // Error State
            <div className="py-6 flex flex-col items-center gap-4">
              <AlertCircle className="h-16 w-16 text-red-600" />
              <div className="text-center space-y-3 w-full">
                <p className="font-semibold text-lg">Authentication Failed</p>
                <Alert variant="destructive">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
                <Button onClick={() => { setState('instructions'); setError(null); }} className="w-full">
                  Try Again
                </Button>
              </div>
            </div>
          ) : state === 'instructions' ? (
            // Instructions State
            <>
              <Alert>
                <Info className="h-4 w-4" />
                <AlertDescription>
                  <p className="font-semibold mb-2">Quick 3-step process:</p>
                  <ol className="text-sm space-y-1.5 list-decimal list-inside">
                    <li>Click "Open Fantrax & Copy Script" below</li>
                    <li>Log in to Fantrax in the new window</li>
                    <li>Open browser console (F12), paste script, press Enter</li>
                  </ol>
                </AlertDescription>
              </Alert>

              <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                <div className="flex items-start gap-2">
                  <ShieldCheck className="h-4 w-4 text-blue-600 mt-0.5 flex-shrink-0" />
                  <div className="text-xs text-blue-900">
                    <p className="font-semibold mb-1">Your credentials are secure</p>
                    <ul className="space-y-0.5 list-disc list-inside text-blue-800">
                      <li>Script only reads cookies (never passwords)</li>
                      <li>You can review the code before running it</li>
                      <li>Cookies are encrypted before storage (AES-256)</li>
                      <li>Login happens entirely in your browser</li>
                    </ul>
                  </div>
                </div>
              </div>

              <Button
                onClick={() => {
                  copyBookmarkletCode();
                  openLoginWindow();
                }}
                className="w-full"
                size="lg"
              >
                <ExternalLink className="mr-2 h-4 w-4" />
                Open Fantrax & Copy Script
              </Button>

              {copied && (
                <Alert>
                  <Check className="h-4 w-4 text-green-600" />
                  <AlertDescription className="text-green-800">
                    Script copied to clipboard! Paste it in the browser console (F12) after logging in.
                  </AlertDescription>
                </Alert>
              )}
            </>
          ) : (
            // Waiting State
            <>
              <div className="py-6 flex flex-col items-center gap-4">
                <Loader2 className="h-12 w-12 animate-spin text-blue-600" />
                <div className="text-center">
                  <p className="font-medium">Waiting for authentication...</p>
                  <p className="text-sm text-muted-foreground mt-1">
                    Complete the steps in the Fantrax window
                  </p>
                </div>
              </div>

              <Alert>
                <Info className="h-4 w-4" />
                <AlertDescription>
                  <p className="text-sm font-semibold mb-2">After logging in to Fantrax:</p>
                  <ol className="text-sm space-y-1 list-decimal list-inside">
                    <li>Press F12 to open browser console</li>
                    <li>Paste the script (already copied to clipboard)</li>
                    <li>Press Enter to run it</li>
                    <li>You'll see a success message</li>
                  </ol>
                </AlertDescription>
              </Alert>

              <div className="space-y-2">
                <Button
                  onClick={copyBookmarkletCode}
                  variant="outline"
                  className="w-full"
                >
                  {copied ? (
                    <>
                      <Check className="mr-2 h-4 w-4 text-green-600" />
                      Copied to Clipboard!
                    </>
                  ) : (
                    <>
                      <Copy className="mr-2 h-4 w-4" />
                      Copy Script Again
                    </>
                  )}
                </Button>

                <Button onClick={handleClose} variant="ghost" className="w-full">
                  Cancel
                </Button>
              </div>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
