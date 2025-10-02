/**
 * Offline status indicator component for mobile
 *
 * @component OfflineIndicator
 * @since 1.0.0
 */

import React, { useState, useEffect } from 'react';
import { Card } from '@/components/ui/card';

/**
 * Props for OfflineIndicator component
 *
 * @interface OfflineIndicatorProps
 */
interface OfflineIndicatorProps {
  /** Position of the indicator (default: 'top') */
  position?: 'top' | 'bottom';

  /** Whether to show sync status (default: true) */
  showSyncStatus?: boolean;

  /** Additional CSS classes */
  className?: string;
}

/**
 * Displays offline/online status and sync state to users
 *
 * Shows banner when offline, indicates when back online
 * Displays background sync status when data is being synchronized
 *
 * @param {OfflineIndicatorProps} props - Component props
 * @returns {JSX.Element | null} Rendered offline indicator
 *
 * @example
 * ```tsx
 * <OfflineIndicator
 *   position="top"
 *   showSyncStatus={true}
 * />
 * ```
 */
export const OfflineIndicator: React.FC<OfflineIndicatorProps> = ({
  position = 'top',
  showSyncStatus = true,
  className = ''
}) => {
  const [isOnline, setIsOnline] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [showReconnected, setShowReconnected] = useState(false);

  useEffect(() => {
    // Check initial online status
    setIsOnline(navigator.onLine);

    /**
     * Handle online event
     */
    const handleOnline = () => {
      setIsOnline(true);
      setShowReconnected(true);

      // Show reconnection message for 3 seconds
      setTimeout(() => {
        setShowReconnected(false);
      }, 3000);

      // Trigger background sync if available
      if ('sync' in self.registration) {
        setIsSyncing(true);
        self.registration.sync.register('sync-data')
          .then(() => {
            setTimeout(() => setIsSyncing(false), 2000);
          })
          .catch(console.error);
      }
    };

    /**
     * Handle offline event
     */
    const handleOffline = () => {
      setIsOnline(false);
      setShowReconnected(false);
    };

    // Add event listeners
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    // Listen for sync events from service worker
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.addEventListener('message', (event) => {
        if (event.data.type === 'SYNC_START') {
          setIsSyncing(true);
        } else if (event.data.type === 'SYNC_COMPLETE') {
          setIsSyncing(false);
        }
      });
    }

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  // Don't show anything if online and not syncing/reconnected
  if (isOnline && !isSyncing && !showReconnected) {
    return null;
  }

  const positionClasses = position === 'top'
    ? 'top-0 animate-slide-down'
    : 'bottom-16 animate-slide-up';

  return (
    <div
      className={`
        fixed left-0 right-0 z-50
        ${positionClasses}
        ${className}
      `}
      role="status"
      aria-live="polite"
    >
      {!isOnline && (
        <Card className="mx-4 my-2 p-3 bg-gray-800 text-white border-gray-700">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <svg
                className="w-5 h-5 text-yellow-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M18.364 5.636a9 9 0 010 12.728m0 0l-2.829-2.829m2.829 2.829L21 21M15.536 8.464a5 5 0 010 7.072m0 0l-2.829-2.829m-4.243 2.829a4.978 4.978 0 01-1.414-2.83m-1.414 5.658a9 9 0 01-2.167-9.238m7.824 2.167a1 1 0 111.414 1.414m-1.414-1.414L3 3m8.293 8.293l1.414 1.414"
                />
              </svg>
              <div>
                <p className="font-medium text-sm">You're offline</p>
                <p className="text-xs text-gray-300">
                  Some features may be limited
                </p>
              </div>
            </div>
          </div>
        </Card>
      )}

      {showReconnected && (
        <Card className="mx-4 my-2 p-3 bg-green-600 text-white border-green-500">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <svg
                className="w-5 h-5 text-white"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M8.111 16.404a5.5 5.5 0 017.778 0M12 20h.01m-7.08-7.071c3.904-3.905 10.236-3.905 14.141 0M1.394 9.393c5.857-5.857 15.355-5.857 21.213 0"
                />
              </svg>
              <div>
                <p className="font-medium text-sm">Back online</p>
                {isSyncing && showSyncStatus && (
                  <p className="text-xs text-green-100">
                    Syncing your data...
                  </p>
                )}
              </div>
            </div>
          </div>
        </Card>
      )}

      {isSyncing && !showReconnected && showSyncStatus && (
        <Card className="mx-4 my-2 p-3 bg-blue-600 text-white border-blue-500">
          <div className="flex items-center gap-2">
            <svg
              className="w-5 h-5 animate-spin"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
            <p className="text-sm font-medium">Syncing data...</p>
          </div>
        </Card>
      )}
    </div>
  );
};

export default OfflineIndicator;