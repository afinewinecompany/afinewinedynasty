/**
 * Fantrax Browser Authentication Modal
 *
 * Opens Fantrax login in user's browser, then extracts cookies client-side.
 * This eliminates the need for server-side browser automation.
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
  RefreshCw
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
  | 'checking'
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
  const [checkAttempts, setCheckAttempts] = useState(0);
  const loginWindowRef = useRef<Window | null>(null);
  const checkIntervalRef = useRef<NodeJS.Timeout | null>(null);

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
   * Open Fantrax login in new window
   */
  const openLoginWindow = () => {
    try {
      // Open Fantrax login in a new window
      const width = 800;
      const height = 700;
      const left = (window.screen.width - width) / 2;
      const top = (window.screen.height - height) / 2;

      const loginWindow = window.open(
        FANTRAX_LOGIN_URL,
        'fantrax_login',
        `width=${width},height=${height},left=${left},top=${top},resizable=yes,scrollbars=yes`
      );

      if (!loginWindow) {
        setError('Failed to open login window. Please allow popups for this site.');
        setState('failed');
        return;
      }

      loginWindowRef.current = loginWindow;
      setState('waiting');
      setCheckAttempts(0);

      // Start checking for login completion
      startChecking();
    } catch (err: any) {
      console.error('Failed to open login window:', err);
      setError(err.message || 'Failed to open login window');
      setState('failed');
    }
  };

  /**
   * Check if user has logged in by attempting to get cookies from the domain
   */
  const checkLoginStatus = async () => {
    const token = getAuthToken();
    if (!token) {
      setError('Not authenticated. Please log in again.');
      setState('failed');
      stopChecking();
      return;
    }

    // Check if window is still open
    if (loginWindowRef.current?.closed) {
      setError('Login window was closed before completing authentication.');
      setState('failed');
      stopChecking();
      return;
    }

    setCheckAttempts(prev => prev + 1);

    // After 60 attempts (2 minutes), time out
    if (checkAttempts >= 60) {
      setError('Authentication timed out. Please try again.');
      setState('failed');
      stopChecking();
      closeLoginWindow();
      return;
    }

    try {
      setState('checking');

      // Try to check if user is logged in by calling our backend
      // which will attempt to verify the session
      const response = await fetch(`${getApiUrl()}/api/v1/fantrax/auth/check-login`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      const data = await response.json();

      if (response.ok && data.is_logged_in) {
        // User is logged in! Capture cookies
        await captureCookies();
      } else {
        // Not logged in yet, keep waiting
        setState('waiting');
      }
    } catch (err: any) {
      console.error('Failed to check login status:', err);
      // Don't fail on network errors, keep checking
      setState('waiting');
    }
  };

  /**
   * Tell user to manually send cookies after logging in
   */
  const captureCookies = async () => {
    const token = getAuthToken();
    if (!token) return;

    try {
      setState('checking');

      // Instruct the popup window to send us its cookies via postMessage
      if (loginWindowRef.current && !loginWindowRef.current.closed) {
        // Inject script to get cookies
        const script = `
          (async function() {
            try {
              // Get all cookies for fantrax.com
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

              // Send cookies back to parent window
              window.opener.postMessage({
                type: 'FANTRAX_COOKIES',
                cookies: cookies
              }, '${window.location.origin}');

              // Close the login window
              window.close();
            } catch (error) {
              console.error('Failed to extract cookies:', error);
              window.opener.postMessage({
                type: 'FANTRAX_COOKIES_ERROR',
                error: error.message
              }, '${window.location.origin}');
            }
          })();
        `;

        // Try to execute the script in the popup
        try {
          loginWindowRef.current.eval(script);
        } catch (err) {
          // Cross-origin restriction - fallback to asking user
          console.error('Cannot access popup cookies due to CORS:', err);
          setError('Please close the Fantrax window after logging in, then click "I\'ve Logged In" below.');
          setState('waiting');
        }
      }
    } catch (err: any) {
      console.error('Failed to capture cookies:', err);
      setError(err.message || 'Failed to capture session');
      setState('failed');
      stopChecking();
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
    } else if (event.data.type === 'FANTRAX_COOKIES_ERROR') {
      setError(event.data.error || 'Failed to extract cookies');
      setState('failed');
    }
  };

  /**
   * Send cookies to backend for storage
   */
  const sendCookiesToBackend = async (cookies: any[]) => {
    const token = getAuthToken();
    if (!token) return;

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
        stopChecking();
        closeLoginWindow();

        // Wait a moment to show success message
        setTimeout(() => {
          onSuccess();
          handleClose();
        }, 1500);
      } else {
        setError(data.detail || 'Failed to save session');
        setState('failed');
        stopChecking();
      }
    } catch (err: any) {
      console.error('Failed to send cookies to backend:', err);
      setError(err.message || 'Failed to save session');
      setState('failed');
      stopChecking();
    }
  };

  /**
   * Manual completion - user confirms they logged in
   */
  const manualComplete = async () => {
    await captureCookies();
  };

  /**
   * Start checking for login completion
   */
  const startChecking = () => {
    if (checkIntervalRef.current) return;

    checkIntervalRef.current = setInterval(() => {
      checkLoginStatus();
    }, 2000); // Check every 2 seconds
  };

  /**
   * Stop checking
   */
  const stopChecking = () => {
    if (checkIntervalRef.current) {
      clearInterval(checkIntervalRef.current);
      checkIntervalRef.current = null;
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
    stopChecking();
    closeLoginWindow();
    setState('instructions');
    setError(null);
    setCheckAttempts(0);
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
      stopChecking();
      closeLoginWindow();
    };
  }, []);

  /**
   * Get status message
   */
  const getStatusMessage = (): string => {
    switch (state) {
      case 'instructions':
        return 'Ready to connect to Fantrax';
      case 'waiting':
        return 'Waiting for you to log in...';
      case 'checking':
        return 'Verifying login...';
      case 'success':
        return 'Successfully connected to Fantrax!';
      case 'failed':
        return error || 'Authentication failed';
      default:
        return 'Processing...';
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Connect to Fantrax</DialogTitle>
          <DialogDescription>
            Log in to Fantrax to connect your account
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
                  <AlertDescription>{getStatusMessage()}</AlertDescription>
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
                  <p className="font-semibold mb-2">How it works:</p>
                  <ol className="text-sm space-y-1.5 list-decimal list-inside">
                    <li>Click "Open Fantrax Login" below</li>
                    <li>A popup window will open</li>
                    <li>Log in to your Fantrax account</li>
                    <li>Your session will be captured automatically</li>
                    <li>The popup will close when done</li>
                  </ol>
                </AlertDescription>
              </Alert>

              <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                <div className="flex items-start gap-2">
                  <ShieldCheck className="h-4 w-4 text-blue-600 mt-0.5 flex-shrink-0" />
                  <div className="text-xs text-blue-900">
                    <p className="font-semibold mb-1">Your credentials are secure</p>
                    <ul className="space-y-0.5 list-disc list-inside text-blue-800">
                      <li>Login happens in your own browser</li>
                      <li>Only session cookies are captured (never passwords)</li>
                      <li>Cookies are encrypted before storage</li>
                      <li>Your data never leaves your device unencrypted</li>
                    </ul>
                  </div>
                </div>
              </div>

              <Button onClick={openLoginWindow} className="w-full" size="lg">
                <ExternalLink className="mr-2 h-4 w-4" />
                Open Fantrax Login
              </Button>
            </>
          ) : (
            // Waiting/Checking State
            <>
              <div className="py-6 flex flex-col items-center gap-4">
                <Loader2 className="h-12 w-12 animate-spin text-blue-600" />
                <div className="text-center">
                  <p className="font-medium">{getStatusMessage()}</p>
                  <p className="text-sm text-muted-foreground mt-1">
                    Check attempt {checkAttempts} of 60
                  </p>
                </div>
              </div>

              <Alert>
                <Info className="h-4 w-4" />
                <AlertDescription>
                  <p className="text-sm">
                    Please complete your login in the popup window.
                    If you've already logged in but nothing happened, click the button below.
                  </p>
                </AlertDescription>
              </Alert>

              <div className="flex gap-2">
                <Button onClick={manualComplete} variant="default" className="flex-1">
                  <RefreshCw className="mr-2 h-4 w-4" />
                  I've Logged In
                </Button>
                <Button onClick={handleClose} variant="outline" className="flex-1">
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
