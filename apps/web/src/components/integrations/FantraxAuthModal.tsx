/**
 * Fantrax In-Browser Authentication Modal
 *
 * Manages server-side Selenium authentication flow with real-time progress indicators.
 * Polls backend for authentication status and provides user feedback.
 *
 * @component FantraxAuthModal
 * @since 1.0.0
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
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, CheckCircle2, XCircle, AlertCircle, Clock } from 'lucide-react';
import * as fantraxApi from '@/lib/api/fantrax';

/**
 * Authentication status types
 */
type AuthStatus =
  | 'idle'
  | 'initializing'
  | 'ready'
  | 'authenticating'
  | 'success'
  | 'failed'
  | 'timeout'
  | 'cancelled';

/**
 * Component props
 */
interface FantraxAuthModalProps {
  /** Whether modal is open */
  isOpen: boolean;
  /** Callback when modal closes */
  onClose: () => void;
  /** Callback on successful authentication */
  onSuccess: () => void;
}

/**
 * In-browser Fantrax authentication modal
 *
 * @param {FantraxAuthModalProps} props - Component props
 * @returns {JSX.Element} Rendered authentication modal
 *
 * @example
 * ```tsx
 * <FantraxAuthModal
 *   isOpen={showModal}
 *   onClose={() => setShowModal(false)}
 *   onSuccess={() => console.log('Connected!')}
 * />
 * ```
 *
 * @since 1.0.0
 */
export function FantraxAuthModal({
  isOpen,
  onClose,
  onSuccess,
}: FantraxAuthModalProps): JSX.Element {
  const [authStatus, setAuthStatus] = useState<AuthStatus>('idle');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [currentUrl, setCurrentUrl] = useState<string | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);
  const [expiresIn, setExpiresIn] = useState<number>(90);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [pollingInterval, setPollingInterval] = useState<NodeJS.Timeout | null>(null);

  /**
   * Start authentication flow
   */
  const initiateAuth = useCallback(async () => {
    try {
      setAuthStatus('initializing');
      setErrorMessage(null);

      const response = await fantraxApi.initiateAuth();
      setSessionId(response.session_id);
      setAuthStatus('initializing');

      // Start status polling
      startPolling(response.session_id);
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to start authentication';
      setErrorMessage(message);
      setAuthStatus('failed');
    }
  }, []);

  /**
   * Poll authentication status
   */
  const startPolling = useCallback((sid: string) => {
    const interval = setInterval(async () => {
      try {
        const status = await fantraxApi.getAuthStatus(sid);

        setAuthStatus(status.status as AuthStatus);
        setCurrentUrl(status.current_url);
        setElapsedSeconds(status.elapsed_seconds);
        setExpiresIn(status.expires_in);

        // Stop polling on terminal states
        if (['success', 'failed', 'timeout', 'cancelled'].includes(status.status)) {
          clearInterval(interval);
          setPollingInterval(null);

          if (status.status === 'success') {
            await completeAuth(sid);
          } else if (status.status === 'timeout') {
            setErrorMessage('Authentication timed out after 90 seconds. Please try again.');
          } else if (status.status === 'failed') {
            setErrorMessage('Authentication failed. Please try again.');
          }
        }
      } catch (error: any) {
        clearInterval(interval);
        setPollingInterval(null);
        const message = error.response?.data?.detail || 'Failed to check authentication status';
        setErrorMessage(message);
        setAuthStatus('failed');
      }
    }, 2000); // Poll every 2 seconds

    setPollingInterval(interval);
  }, []);

  /**
   * Complete authentication and capture cookies
   */
  const completeAuth = async (sid: string): Promise<void> => {
    try {
      await fantraxApi.completeAuth(sid);
      setAuthStatus('success');

      // Call success callback after short delay
      setTimeout(() => {
        onSuccess();
        handleClose();
      }, 1500);
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to complete authentication';
      setErrorMessage(message);
      setAuthStatus('failed');
    }
  };

  /**
   * Cancel authentication
   */
  const handleCancel = async (): Promise<void> => {
    if (sessionId && authStatus !== 'success') {
      try {
        await fantraxApi.cancelAuth(sessionId);
      } catch (error) {
        console.error('Failed to cancel auth:', error);
      }
    }

    if (pollingInterval) {
      clearInterval(pollingInterval);
      setPollingInterval(null);
    }

    handleClose();
  };

  /**
   * Close modal and reset state
   */
  const handleClose = (): void => {
    if (pollingInterval) {
      clearInterval(pollingInterval);
      setPollingInterval(null);
    }

    setAuthStatus('idle');
    setSessionId(null);
    setCurrentUrl(null);
    setElapsedSeconds(0);
    setExpiresIn(90);
    setErrorMessage(null);

    onClose();
  };

  /**
   * Retry authentication
   */
  const handleRetry = (): void => {
    setAuthStatus('idle');
    setErrorMessage(null);
    initiateAuth();
  };

  /**
   * Initialize auth when modal opens
   */
  useEffect(() => {
    if (isOpen && authStatus === 'idle') {
      initiateAuth();
    }
  }, [isOpen, authStatus, initiateAuth]);

  /**
   * Cleanup on unmount
   */
  useEffect(() => {
    return () => {
      if (pollingInterval) {
        clearInterval(pollingInterval);
      }
    };
  }, [pollingInterval]);

  /**
   * Get progress percentage based on status
   */
  const getProgressValue = (): number => {
    switch (authStatus) {
      case 'idle':
        return 0;
      case 'initializing':
        return 20;
      case 'ready':
        return 50;
      case 'authenticating':
        return 80;
      case 'success':
        return 100;
      default:
        return 50;
    }
  };

  /**
   * Get status icon
   */
  const getStatusIcon = (): JSX.Element => {
    switch (authStatus) {
      case 'success':
        return <CheckCircle2 className="h-12 w-12 text-green-600" />;
      case 'failed':
      case 'timeout':
        return <XCircle className="h-12 w-12 text-red-600" />;
      case 'authenticating':
        return <Loader2 className="h-12 w-12 text-blue-600 animate-spin" />;
      default:
        return <Loader2 className="h-12 w-12 text-blue-600 animate-spin" />;
    }
  };

  /**
   * Get user-friendly status message
   */
  const getStatusMessage = (): string => {
    switch (authStatus) {
      case 'idle':
        return 'Preparing authentication...';
      case 'initializing':
        return 'Initializing browser... (5-15 seconds)';
      case 'ready':
        return 'Please log in to Fantrax in your browser';
      case 'authenticating':
        return 'Detecting login... Please wait';
      case 'success':
        return 'Successfully connected to Fantrax!';
      case 'failed':
        return 'Authentication failed';
      case 'timeout':
        return 'Authentication timed out';
      case 'cancelled':
        return 'Authentication cancelled';
      default:
        return 'Processing...';
    }
  };

  /**
   * Check if in terminal state
   */
  const isTerminalState = (): boolean => {
    return ['success', 'failed', 'timeout', 'cancelled'].includes(authStatus);
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Connect to Fantrax</DialogTitle>
          <DialogDescription>
            {isTerminalState()
              ? 'Authentication process complete'
              : 'Secure server-side authentication in progress'}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* Status Icon */}
          <div className="flex justify-center">{getStatusIcon()}</div>

          {/* Progress Bar */}
          {!isTerminalState() && (
            <div className="space-y-2">
              <Progress value={getProgressValue()} className="w-full" />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>Elapsed: {elapsedSeconds}s</span>
                <span>Timeout in: {expiresIn}s</span>
              </div>
            </div>
          )}

          {/* Status Message */}
          <div className="text-center space-y-2">
            <p className="font-medium">{getStatusMessage()}</p>
            {authStatus === 'ready' && (
              <div className="text-sm text-muted-foreground space-y-1">
                <p>A secure browser session has been opened.</p>
                <p>Log in to Fantrax using your credentials.</p>
                <p className="flex items-center justify-center gap-1 text-xs">
                  <Clock className="h-3 w-3" />
                  This typically takes 30-60 seconds
                </p>
              </div>
            )}
            {authStatus === 'authenticating' && (
              <p className="text-sm text-muted-foreground">
                Login detected! Capturing authentication...
              </p>
            )}
          </div>

          {/* Error Message */}
          {errorMessage && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{errorMessage}</AlertDescription>
            </Alert>
          )}

          {/* Action Buttons */}
          <div className="flex gap-2">
            {authStatus === 'success' ? (
              <Button onClick={handleClose} className="w-full">
                Done
              </Button>
            ) : authStatus === 'failed' || authStatus === 'timeout' ? (
              <>
                <Button variant="outline" onClick={handleClose} className="w-full">
                  Close
                </Button>
                <Button onClick={handleRetry} className="w-full">
                  Retry
                </Button>
              </>
            ) : (
              <Button
                variant="outline"
                onClick={handleCancel}
                className="w-full"
                disabled={authStatus === 'success'}
              >
                Cancel
              </Button>
            )}
          </div>

          {/* Help Text */}
          {authStatus === 'ready' && (
            <div className="text-xs text-muted-foreground text-center space-y-1 pt-2 border-t">
              <p className="font-medium">Having trouble?</p>
              <ul className="space-y-1">
                <li>• Make sure pop-ups are not blocked</li>
                <li>• Check that you're using correct Fantrax credentials</li>
                <li>• Try refreshing and starting again if stuck</li>
              </ul>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
