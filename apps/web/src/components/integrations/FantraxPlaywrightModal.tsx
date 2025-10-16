/**
 * Fantrax Playwright Authentication Modal
 *
 * Provides seamless in-browser authentication using Playwright on the backend.
 * User logs in through their browser while this component polls for status.
 *
 * @component FantraxPlaywrightModal
 * @since 1.1.0
 */

'use client';

import React, { useState, useEffect, useCallback } from 'react';
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
  Clock,
  Browser,
  ShieldCheck,
  Info
} from 'lucide-react';
import { Progress } from '@/components/ui/progress';

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
 * Authentication session status
 */
type SessionStatus =
  | 'initializing'
  | 'ready'
  | 'authenticating'
  | 'success'
  | 'failed'
  | 'timeout'
  | 'cancelled';

/**
 * Fantrax Playwright authentication modal
 *
 * @param {FantraxPlaywrightModalProps} props - Component props
 * @returns {JSX.Element} Rendered authentication modal
 *
 * @example
 * ```tsx
 * <FantraxPlaywrightModal
 *   isOpen={showModal}
 *   onClose={() => setShowModal(false)}
 *   onSuccess={() => console.log('Connected!')}
 * />
 * ```
 *
 * @since 1.1.0
 */
export function FantraxPlaywrightModal({
  isOpen,
  onClose,
  onSuccess,
}: FantraxPlaywrightModalProps): JSX.Element {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState<SessionStatus>('initializing');
  const [currentUrl, setCurrentUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [expiresIn, setExpiresIn] = useState(90);

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
   * Initiate authentication session
   */
  const initiateAuth = useCallback(async () => {
    const token = getAuthToken();
    if (!token) {
      setError('Not authenticated. Please log in again.');
      setStatus('failed');
      return;
    }

    try {
      const response = await fetch(`${getApiUrl()}/api/v1/fantrax/auth/initiate`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      const data = await response.json();

      if (response.ok) {
        setSessionId(data.session_id);
        setStatus('ready');
        setExpiresIn(data.expires_in || 90);
      } else {
        setError(data.detail || 'Failed to start authentication session');
        setStatus('failed');
      }
    } catch (err: any) {
      console.error('Failed to initiate auth:', err);
      setError(err.message || 'Failed to connect to server');
      setStatus('failed');
    }
  }, []);

  /**
   * Poll session status
   */
  const pollStatus = useCallback(async () => {
    if (!sessionId) return;

    const token = getAuthToken();
    if (!token) return;

    try {
      const response = await fetch(
        `${getApiUrl()}/api/v1/fantrax/auth/status/${sessionId}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        }
      );

      const data = await response.json();

      if (response.ok) {
        setStatus(data.status);
        setCurrentUrl(data.current_url);
        setElapsedSeconds(data.elapsed_seconds || 0);
        setExpiresIn(data.expires_in || 0);

        // If user logged in, complete the authentication
        if (data.status === 'authenticating') {
          await completeAuth();
        }
      } else {
        // Session may have expired or been cancelled
        if (response.status === 410) {
          setError('Authentication timed out. Please try again.');
          setStatus('timeout');
        } else {
          setError(data.detail || 'Failed to check status');
          setStatus('failed');
        }
      }
    } catch (err: any) {
      console.error('Failed to poll status:', err);
      // Don't set error for network issues - keep polling
    }
  }, [sessionId]);

  /**
   * Complete authentication and capture cookies
   */
  const completeAuth = async () => {
    if (!sessionId) return;

    const token = getAuthToken();
    if (!token) return;

    try {
      const response = await fetch(
        `${getApiUrl()}/api/v1/fantrax/auth/complete/${sessionId}`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        }
      );

      const data = await response.json();

      if (response.ok && data.success) {
        setStatus('success');
        // Wait a moment to show success message
        setTimeout(() => {
          onSuccess();
          handleClose();
        }, 1500);
      } else {
        setError(data.detail || 'Failed to complete authentication');
        setStatus('failed');
      }
    } catch (err: any) {
      console.error('Failed to complete auth:', err);
      setError(err.message || 'Failed to complete authentication');
      setStatus('failed');
    }
  };

  /**
   * Cancel authentication session
   */
  const cancelAuth = async () => {
    if (!sessionId) {
      handleClose();
      return;
    }

    const token = getAuthToken();
    if (!token) {
      handleClose();
      return;
    }

    try {
      await fetch(`${getApiUrl()}/api/v1/fantrax/auth/cancel/${sessionId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });
    } catch (err) {
      console.error('Failed to cancel auth:', err);
    }

    handleClose();
  };

  /**
   * Close modal and reset state
   */
  const handleClose = () => {
    setSessionId(null);
    setStatus('initializing');
    setCurrentUrl(null);
    setError(null);
    setElapsedSeconds(0);
    setExpiresIn(90);
    onClose();
  };

  /**
   * Start authentication when modal opens
   */
  useEffect(() => {
    if (isOpen && !sessionId) {
      initiateAuth();
    }
  }, [isOpen, sessionId, initiateAuth]);

  /**
   * Poll status every 2 seconds when session is active
   */
  useEffect(() => {
    if (!sessionId || status === 'success' || status === 'failed' || status === 'timeout') {
      return;
    }

    const interval = setInterval(pollStatus, 2000);
    return () => clearInterval(interval);
  }, [sessionId, status, pollStatus]);

  /**
   * Get status message
   */
  const getStatusMessage = (): string => {
    switch (status) {
      case 'initializing':
        return 'Initializing browser session...';
      case 'ready':
        return 'Please log in to Fantrax in the browser window';
      case 'authenticating':
        return 'Login detected! Capturing session...';
      case 'success':
        return 'Successfully connected to Fantrax!';
      case 'failed':
        return error || 'Authentication failed';
      case 'timeout':
        return 'Authentication timed out after 90 seconds';
      case 'cancelled':
        return 'Authentication cancelled';
      default:
        return 'Processing...';
    }
  };

  /**
   * Get progress percentage
   */
  const getProgress = (): number => {
    if (status === 'success') return 100;
    if (status === 'failed' || status === 'timeout') return 0;
    if (status === 'authenticating') return 75;
    if (status === 'ready') return 50;
    if (status === 'initializing') return 25;
    return 0;
  };

  return (
    <Dialog open={isOpen} onOpenChange={cancelAuth}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Connect to Fantrax</DialogTitle>
          <DialogDescription>
            Authenticating via secure browser session
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Status Display */}
          {status === 'success' ? (
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
          ) : status === 'failed' || status === 'timeout' ? (
            // Error State
            <div className="py-6 flex flex-col items-center gap-4">
              <AlertCircle className="h-16 w-16 text-red-600" />
              <div className="text-center space-y-3 w-full">
                <p className="font-semibold text-lg">Authentication Failed</p>
                <Alert variant="destructive">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>{getStatusMessage()}</AlertDescription>
                </Alert>
                <Button onClick={initiateAuth} className="w-full">
                  Try Again
                </Button>
              </div>
            </div>
          ) : (
            // In Progress State
            <>
              {/* Progress Bar */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Progress</span>
                  <span className="text-muted-foreground">
                    {expiresIn > 0 ? `${expiresIn}s remaining` : 'Completing...'}
                  </span>
                </div>
                <Progress value={getProgress()} className="h-2" />
              </div>

              {/* Status Icon and Message */}
              <div className="flex flex-col items-center gap-4 py-4">
                {status === 'initializing' && (
                  <Loader2 className="h-12 w-12 animate-spin text-blue-600" />
                )}
                {status === 'ready' && (
                  <Browser className="h-12 w-12 text-blue-600" />
                )}
                {status === 'authenticating' && (
                  <Loader2 className="h-12 w-12 animate-spin text-green-600" />
                )}

                <div className="text-center">
                  <p className="font-medium">{getStatusMessage()}</p>
                  {elapsedSeconds > 0 && (
                    <p className="text-sm text-muted-foreground mt-1 flex items-center justify-center gap-1">
                      <Clock className="h-3 w-3" />
                      {elapsedSeconds} seconds elapsed
                    </p>
                  )}
                </div>
              </div>

              {/* Instructions */}
              {status === 'ready' && (
                <Alert>
                  <Info className="h-4 w-4" />
                  <AlertDescription>
                    <p className="font-semibold mb-2">How to connect:</p>
                    <ol className="text-sm space-y-1 list-decimal list-inside">
                      <li>A browser window has opened on our server</li>
                      <li>Enter your Fantrax credentials in that browser</li>
                      <li>Once logged in, we'll detect it automatically</li>
                      <li>Your session will be captured securely</li>
                    </ol>
                  </AlertDescription>
                </Alert>
              )}

              {/* Security Notice */}
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                <div className="flex items-start gap-2">
                  <ShieldCheck className="h-4 w-4 text-blue-600 mt-0.5 flex-shrink-0" />
                  <div className="text-xs text-blue-900">
                    <p className="font-semibold mb-1">Your credentials are secure</p>
                    <ul className="space-y-0.5 list-disc list-inside text-blue-800">
                      <li>Login happens in an isolated browser session</li>
                      <li>Only encrypted session cookies are saved</li>
                      <li>Passwords are never stored or transmitted</li>
                    </ul>
                  </div>
                </div>
              </div>

              {/* Cancel Button */}
              <Button
                variant="outline"
                onClick={cancelAuth}
                className="w-full"
                disabled={status === 'authenticating'}
              >
                Cancel
              </Button>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
