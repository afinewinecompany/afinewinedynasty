/**
 * Fantrax Connection Component
 *
 * Manages Fantrax OAuth connection and displays connection status.
 * Allows users to connect/disconnect their Fantrax account.
 *
 * @component FantraxConnection
 * @since 1.0.0
 */

'use client';

import React from 'react';
import { useFantrax } from '@/hooks/useFantrax';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { CheckCircle2, XCircle, Loader2, Link as LinkIcon } from 'lucide-react';

/**
 * Component props
 */
interface FantraxConnectionProps {
  /** Optional callback when connection status changes */
  onConnectionChange?: (connected: boolean) => void;
  /** Whether to show compact view */
  compact?: boolean;
}

/**
 * Fantrax connection management component
 *
 * @param props - Component props
 * @returns Rendered component
 *
 * @example
 * ```tsx
 * <FantraxConnection onConnectionChange={(connected) => console.log('Connected:', connected)} />
 * ```
 *
 * @since 1.0.0
 */
export function FantraxConnection({ onConnectionChange, compact = false }: FantraxConnectionProps) {
  const {
    isConnected,
    leagues,
    loading,
    error,
    connect,
    disconnect,
  } = useFantrax();

  // Notify parent of connection changes
  React.useEffect(() => {
    onConnectionChange?.(isConnected);
  }, [isConnected, onConnectionChange]);

  if (compact) {
    return (
      <div className="flex items-center gap-2">
        {isConnected ? (
          <>
            <CheckCircle2 className="h-5 w-5 text-green-600" />
            <span className="text-sm text-green-600">Connected to Fantrax</span>
            <Button
              variant="ghost"
              size="sm"
              onClick={disconnect}
              disabled={loading.connection}
            >
              Disconnect
            </Button>
          </>
        ) : (
          <>
            <XCircle className="h-5 w-5 text-gray-400" />
            <span className="text-sm text-gray-600">Not connected</span>
            <Button
              variant="outline"
              size="sm"
              onClick={connect}
              disabled={loading.connection}
            >
              {loading.connection ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Connecting...
                </>
              ) : (
                <>
                  <LinkIcon className="mr-2 h-4 w-4" />
                  Connect Fantrax
                </>
              )}
            </Button>
          </>
        )}
      </div>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <LinkIcon className="h-5 w-5" />
          Fantrax Integration
        </CardTitle>
        <CardDescription>
          Connect your Fantrax account to get personalized prospect recommendations
          based on your league rosters.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Connection Status */}
        <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
          <div className="flex items-center gap-3">
            {isConnected ? (
              <CheckCircle2 className="h-6 w-6 text-green-600" />
            ) : (
              <XCircle className="h-6 w-6 text-gray-400" />
            )}
            <div>
              <p className="font-medium">
                {isConnected ? 'Connected to Fantrax' : 'Not Connected'}
              </p>
              {isConnected && (
                <p className="text-sm text-gray-600">
                  {leagues.length} {leagues.length === 1 ? 'league' : 'leagues'} found
                </p>
              )}
            </div>
          </div>
          <Button
            onClick={isConnected ? disconnect : connect}
            disabled={loading.connection}
            variant={isConnected ? 'outline' : 'default'}
          >
            {loading.connection ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {isConnected ? 'Disconnecting...' : 'Connecting...'}
              </>
            ) : isConnected ? (
              'Disconnect'
            ) : (
              <>
                <LinkIcon className="mr-2 h-4 w-4" />
                Connect Fantrax
              </>
            )}
          </Button>
        </div>

        {/* Error Message */}
        {error.connection && (
          <Alert variant="destructive">
            <AlertDescription>{error.connection}</AlertDescription>
          </Alert>
        )}

        {/* Connection Benefits */}
        {!isConnected && (
          <div className="space-y-2 pt-4">
            <p className="font-medium text-sm">Benefits of connecting:</p>
            <ul className="text-sm text-gray-600 space-y-1 list-disc list-inside">
              <li>Get prospect recommendations tailored to your team needs</li>
              <li>Analyze your roster depth and identify future holes</li>
              <li>Receive trade suggestions based on your league settings</li>
              <li>Track multiple dynasty leagues in one place</li>
            </ul>
          </div>
        )}

        {/* Premium Notice */}
        <div className="pt-4 border-t">
          <p className="text-xs text-gray-500">
            🔒 Fantrax integration is a premium feature. Upgrade to access personalized
            recommendations and advanced roster analysis.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
