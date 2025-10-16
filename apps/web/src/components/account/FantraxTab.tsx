/**
 * Fantrax Integration Tab Component
 *
 * Manages Fantrax account connection, league selection, and roster syncing.
 * Provides in-browser authentication flow with real-time progress indicators.
 *
 * @component FantraxTab
 * @since 1.0.0
 */

'use client';

import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { useFantrax } from '@/hooks/useFantrax';
import { useAuth } from '@/hooks/useAuth';
import { FantraxLoginModal } from '@/components/integrations/FantraxLoginModal';
import { LeagueSelector } from '@/components/integrations/LeagueSelector';
import { RosterDisplay } from '@/components/integrations/RosterDisplay';
import {
  CheckCircle2,
  XCircle,
  Loader2,
  Link as LinkIcon,
  RefreshCw,
  AlertCircle,
  Crown,
} from 'lucide-react';

/**
 * Fantrax integration management tab
 *
 * @returns {JSX.Element} Rendered Fantrax integration interface
 *
 * @example
 * ```tsx
 * <FantraxTab />
 * ```
 *
 * @since 1.0.0
 */
export function FantraxTab(): JSX.Element {
  const { user } = useAuth();
  const {
    isConnected,
    leagues,
    selectedLeague,
    roster,
    loading,
    error,
    disconnect,
    selectLeague,
    syncRoster,
    checkConnection,
  } = useFantrax();

  const [showAuthModal, setShowAuthModal] = useState(false);

  const isPremium = user?.subscriptionTier === 'premium';

  /**
   * Handle successful authentication
   */
  const handleAuthSuccess = async (): Promise<void> => {
    setShowAuthModal(false);
    await checkConnection();
  };

  /**
   * Handle disconnect button click
   */
  const handleDisconnect = async (): Promise<void> => {
    if (confirm('Are you sure you want to disconnect your Fantrax account?')) {
      await disconnect();
    }
  };

  /**
   * Handle manual roster sync
   */
  const handleSync = async (): Promise<void> => {
    if (selectedLeague) {
      await syncRoster(false);
    }
  };

  // Premium gate
  if (!isPremium) {
    return (
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Crown className="h-5 w-5 text-yellow-500" />
            <CardTitle>Fantrax Integration</CardTitle>
            <Badge variant="secondary">Premium</Badge>
          </div>
          <CardDescription>
            Connect your Fantrax account to access personalized prospect recommendations
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="p-6 bg-gradient-to-br from-yellow-50 to-orange-50 rounded-lg border-2 border-yellow-200">
            <h3 className="font-semibold text-lg mb-2">Upgrade to Premium</h3>
            <p className="text-sm text-muted-foreground mb-4">
              Fantrax integration is a premium feature. Unlock personalized prospect
              recommendations based on your team needs.
            </p>
            <ul className="text-sm text-muted-foreground space-y-1 mb-4 list-disc list-inside">
              <li>Connect unlimited dynasty leagues</li>
              <li>Automatic roster sync</li>
              <li>Team needs analysis</li>
              <li>Personalized prospect recommendations</li>
            </ul>
            <Button className="w-full" onClick={() => window.location.href = '/subscription'}>
              Upgrade Now - $9.99/month
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Connection Status Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <LinkIcon className="h-5 w-5" />
            Fantrax Connection
          </CardTitle>
          <CardDescription>
            Connect your Fantrax account to sync your dynasty league rosters
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Connection Status Display */}
          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
            <div className="flex items-center gap-3">
              {isConnected ? (
                <>
                  <CheckCircle2 className="h-6 w-6 text-green-600" />
                  <div>
                    <p className="font-medium">Connected to Fantrax</p>
                    {leagues.length > 0 && (
                      <p className="text-sm text-gray-600">
                        {leagues.length} {leagues.length === 1 ? 'league' : 'leagues'} found
                      </p>
                    )}
                  </div>
                </>
              ) : (
                <>
                  <XCircle className="h-6 w-6 text-gray-400" />
                  <div>
                    <p className="font-medium">Not Connected</p>
                    <p className="text-sm text-gray-600">Connect to access your leagues</p>
                  </div>
                </>
              )}
            </div>

            {/* Action Buttons */}
            <div>
              {isConnected ? (
                <Button
                  variant="outline"
                  onClick={handleDisconnect}
                  disabled={loading.connection}
                >
                  {loading.connection ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Disconnecting...
                    </>
                  ) : (
                    'Disconnect'
                  )}
                </Button>
              ) : (
                <Button onClick={() => setShowAuthModal(true)} disabled={loading.connection}>
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
              )}
            </div>
          </div>

          {/* Error Display */}
          {error.connection && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error.connection}</AlertDescription>
            </Alert>
          )}

          {/* Connection Benefits (when disconnected) */}
          {!isConnected && (
            <div className="space-y-2 pt-4 border-t">
              <p className="font-medium text-sm">Benefits of connecting:</p>
              <ul className="text-sm text-gray-600 space-y-1 list-disc list-inside">
                <li>Get prospect recommendations tailored to your team needs</li>
                <li>Analyze your roster depth and identify future holes</li>
                <li>Sync multiple dynasty leagues in one place</li>
                <li>Track roster changes and league activity</li>
              </ul>
            </div>
          )}
        </CardContent>
      </Card>

      {/* League Management (only when connected) */}
      {isConnected && leagues.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>League Management</CardTitle>
            <CardDescription>Select a league to view roster and sync data</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <LeagueSelector
              leagues={leagues}
              selectedLeague={selectedLeague}
              onSelectLeague={selectLeague}
              isLoading={loading.leagues}
            />

            {selectedLeague && (
              <div className="flex items-center justify-between pt-4 border-t">
                <div>
                  <p className="text-sm font-medium">Roster Sync</p>
                  <p className="text-xs text-muted-foreground">
                    {roster?.last_sync
                      ? `Last synced: ${new Date(roster.last_sync).toLocaleString()}`
                      : 'Never synced'}
                  </p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleSync}
                  disabled={loading.sync}
                >
                  {loading.sync ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Syncing...
                    </>
                  ) : (
                    <>
                      <RefreshCw className="mr-2 h-4 w-4" />
                      Sync Roster
                    </>
                  )}
                </Button>
              </div>
            )}

            {error.sync && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error.sync}</AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>
      )}

      {/* Roster Display (when league selected and synced) */}
      {isConnected && selectedLeague && roster && (
        <RosterDisplay roster={roster} isLoading={loading.roster} />
      )}

      {/* Login Modal */}
      <FantraxLoginModal
        isOpen={showAuthModal}
        onClose={() => setShowAuthModal(false)}
        onSuccess={handleAuthSuccess}
      />
    </div>
  );
}
