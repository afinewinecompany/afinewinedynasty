/**
 * Pull-to-refresh component for mobile data updates
 *
 * @component PullToRefresh
 * @since 1.0.0
 */

import React, { useState, useRef, useCallback, ReactNode } from 'react';

/**
 * Props for PullToRefresh component
 *
 * @interface PullToRefreshProps
 */
interface PullToRefreshProps {
  /** Child content to wrap */
  children: ReactNode;

  /** Async function to call when refresh is triggered */
  onRefresh: () => Promise<void>;

  /** Whether component is enabled (default: true) */
  enabled?: boolean;

  /** Pull distance threshold to trigger refresh (default: 80px) */
  threshold?: number;

  /** Additional CSS classes */
  className?: string;
}

/**
 * Pull-to-refresh wrapper for mobile content updates
 *
 * Implements pull-down gesture to trigger data refresh with visual feedback
 * Shows loading indicator during refresh operation
 *
 * @param {PullToRefreshProps} props - Component props
 * @returns {JSX.Element} Children wrapped with pull-to-refresh functionality
 *
 * @example
 * ```tsx
 * <PullToRefresh
 *   onRefresh={async () => await fetchLatestData()}
 * >
 *   <ProspectRankings />
 * </PullToRefresh>
 * ```
 */
export const PullToRefresh: React.FC<PullToRefreshProps> = ({
  children,
  onRefresh,
  enabled = true,
  threshold = 80,
  className = ''
}) => {
  const [pullDistance, setPullDistance] = useState(0);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isPulling, setIsPulling] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const startYRef = useRef<number>(0);

  /**
   * Handle touch start event
   */
  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    if (!enabled || isRefreshing) return;

    const touch = e.touches[0];
    startYRef.current = touch.clientY;

    // Check if we're at the top of the scrollable area
    const scrollTop = containerRef.current?.scrollTop || 0;
    if (scrollTop === 0) {
      setIsPulling(true);
    }
  }, [enabled, isRefreshing]);

  /**
   * Handle touch move event
   */
  const handleTouchMove = useCallback((e: React.TouchEvent) => {
    if (!enabled || !isPulling || isRefreshing) return;

    const touch = e.touches[0];
    const currentY = touch.clientY;
    const diff = currentY - startYRef.current;

    // Only track downward pull when at top
    if (diff > 0 && containerRef.current?.scrollTop === 0) {
      e.preventDefault(); // Prevent default scroll

      // Apply resistance factor for more natural feel
      const resistance = 0.5;
      const adjustedDistance = diff * resistance;

      setPullDistance(Math.min(adjustedDistance, threshold * 1.5));
    }
  }, [enabled, isPulling, isRefreshing, threshold]);

  /**
   * Handle touch end event
   */
  const handleTouchEnd = useCallback(async () => {
    if (!enabled || !isPulling) return;

    setIsPulling(false);

    // Check if pull distance exceeds threshold
    if (pullDistance >= threshold) {
      setIsRefreshing(true);
      setPullDistance(60); // Keep indicator visible during refresh

      try {
        await onRefresh();
      } catch (error) {
        console.error('Refresh failed:', error);
      } finally {
        setIsRefreshing(false);
        setPullDistance(0);
      }
    } else {
      // Snap back if threshold not met
      setPullDistance(0);
    }
  }, [enabled, isPulling, pullDistance, threshold, onRefresh]);

  // Calculate rotation for spinner based on pull distance
  const getSpinnerRotation = () => {
    if (isRefreshing) return 'animate-spin';
    const rotation = (pullDistance / threshold) * 360;
    return `rotate(${rotation}deg)`;
  };

  // Calculate opacity based on pull distance
  const getOpacity = () => {
    return Math.min(pullDistance / threshold, 1);
  };

  return (
    <div className={`relative ${className}`}>
      {/* Pull indicator */}
      <div
        className={`
          absolute top-0 left-0 right-0
          flex justify-center items-center
          transition-transform duration-200 ease-out
          pointer-events-none z-10
        `}
        style={{
          transform: `translateY(${pullDistance - 60}px)`,
          height: '60px'
        }}
      >
        <div
          className={`
            flex items-center justify-center
            w-10 h-10 rounded-full bg-white shadow-lg
          `}
          style={{ opacity: getOpacity() }}
        >
          {isRefreshing ? (
            <svg
              className="animate-spin h-6 w-6 text-blue-600"
              xmlns="http://www.w3.org/2000/svg"
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
          ) : (
            <svg
              className="h-6 w-6 text-blue-600 transition-transform"
              style={{ transform: getSpinnerRotation() }}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              />
            </svg>
          )}
        </div>
      </div>

      {/* Content container */}
      <div
        ref={containerRef}
        className={`
          relative overflow-auto
          transition-transform duration-200 ease-out
        `}
        style={{
          transform: `translateY(${pullDistance}px)`
        }}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
      >
        {children}
      </div>
    </div>
  );
};

export default PullToRefresh;