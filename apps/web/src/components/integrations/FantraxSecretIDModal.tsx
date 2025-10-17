/**
 * Fantrax Secret ID Authentication Modal
 *
 * Simple modal for users to input their Fantrax Secret ID.
 * The Secret ID can be found on the user's Fantrax profile page.
 *
 * @component FantraxSecretIDModal
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
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Loader2, ExternalLink, CheckCircle2, Info } from 'lucide-react';

interface FantraxSecretIDModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

/**
 * Modal for Fantrax Secret ID input
 *
 * @param {FantraxSecretIDModalProps} props - Component props
 * @returns {JSX.Element} Rendered modal
 *
 * @example
 * ```tsx
 * <FantraxSecretIDModal
 *   isOpen={showModal}
 *   onClose={() => setShowModal(false)}
 *   onSuccess={handleAuthSuccess}
 * />
 * ```
 */
export function FantraxSecretIDModal({
  isOpen,
  onClose,
  onSuccess,
}: FantraxSecretIDModalProps): JSX.Element {
  const [secretId, setSecretId] = useState('');
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  /**
   * Handle form submission
   */
  const handleConnect = async () => {
    if (!secretId.trim()) {
      setError('Please enter your Secret ID');
      return;
    }

    setIsConnecting(true);
    setError(null);

    try {
      const token = localStorage.getItem('access_token');
      if (!token) {
        throw new Error('Not authenticated');
      }

      const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(`${API_BASE_URL}/api/v1/fantrax/connect`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ secret_id: secretId }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to connect Fantrax account');
      }

      const data = await response.json();

      setSuccess(true);
      setSecretId('');

      // Show success message briefly, then close and trigger success callback
      setTimeout(() => {
        onSuccess();
        handleClose();
      }, 1500);
    } catch (err) {
      console.error('Failed to connect Fantrax:', err);
      setError(
        err instanceof Error
          ? err.message
          : 'Failed to connect. Please check your Secret ID and try again.'
      );
    } finally {
      setIsConnecting(false);
    }
  };

  /**
   * Handle modal close
   */
  const handleClose = () => {
    setSecretId('');
    setError(null);
    setSuccess(false);
    onClose();
  };

  /**
   * Handle Enter key press
   */
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !isConnecting && secretId.trim()) {
      handleConnect();
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Connect Fantrax Account</DialogTitle>
          <DialogDescription>
            Enter your Fantrax Secret ID to connect your account
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Instructions */}
          <Alert>
            <Info className="h-4 w-4" />
            <AlertDescription className="text-sm">
              <p className="font-medium mb-2">How to find your Secret ID:</p>
              <ol className="list-decimal list-inside space-y-1 text-xs">
                <li>Log in to your Fantrax account</li>
                <li>Go to your User Profile page</li>
                <li>Look for &quot;Secret ID&quot; in your profile</li>
                <li>Copy the ID and paste it below</li>
              </ol>
            </AlertDescription>
          </Alert>

          {/* Input Field */}
          <div className="space-y-2">
            <Label htmlFor="secret-id">Secret ID</Label>
            <Input
              id="secret-id"
              type="text"
              placeholder="Enter your Fantrax Secret ID"
              value={secretId}
              onChange={(e) => setSecretId(e.target.value)}
              onKeyPress={handleKeyPress}
              disabled={isConnecting || success}
              className="font-mono text-sm"
            />
            <p className="text-xs text-muted-foreground">
              Example: 24pscnquxwekzngy
            </p>
          </div>

          {/* Error Message */}
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* Success Message */}
          {success && (
            <Alert className="border-green-200 bg-green-50">
              <CheckCircle2 className="h-4 w-4 text-green-600" />
              <AlertDescription className="text-green-800">
                Successfully connected! Loading your leagues...
              </AlertDescription>
            </Alert>
          )}

          {/* Help Link */}
          <div className="flex items-center justify-center">
            <a
              href="https://www.fantrax.com/profile"
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-blue-600 hover:text-blue-800 flex items-center gap-1"
            >
              Open Fantrax Profile
              <ExternalLink className="h-3 w-3" />
            </a>
          </div>

          {/* Action Buttons */}
          <div className="flex gap-2 pt-2">
            <Button
              variant="outline"
              onClick={handleClose}
              disabled={isConnecting || success}
              className="flex-1"
            >
              Cancel
            </Button>
            <Button
              onClick={handleConnect}
              disabled={isConnecting || success || !secretId.trim()}
              className="flex-1"
            >
              {isConnecting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Connecting...
                </>
              ) : success ? (
                <>
                  <CheckCircle2 className="mr-2 h-4 w-4" />
                  Connected!
                </>
              ) : (
                'Connect'
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
