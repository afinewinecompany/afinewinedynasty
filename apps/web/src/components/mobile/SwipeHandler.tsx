/**
 * Touch gesture handler wrapper component for swipe interactions
 *
 * @component SwipeHandler
 * @since 1.0.0
 */

import React, { useRef, useEffect, ReactNode } from 'react';

/**
 * Swipe direction enumeration
 *
 * @enum SwipeDirection
 */
export type SwipeDirection = 'left' | 'right' | 'up' | 'down';

/**
 * Props for SwipeHandler component
 *
 * @interface SwipeHandlerProps
 */
interface SwipeHandlerProps {
  /** Child elements to wrap with swipe detection */
  children: ReactNode;

  /** Callback when swipe is detected */
  onSwipe?: (direction: SwipeDirection) => void;

  /** Callback specifically for left swipe */
  onSwipeLeft?: () => void;

  /** Callback specifically for right swipe */
  onSwipeRight?: () => void;

  /** Callback specifically for up swipe */
  onSwipeUp?: () => void;

  /** Callback specifically for down swipe */
  onSwipeDown?: () => void;

  /** Minimum swipe distance in pixels to trigger (default: 50) */
  threshold?: number;

  /** Whether swipe detection is enabled (default: true) */
  enabled?: boolean;

  /** Additional CSS classes */
  className?: string;
}

/**
 * Wrapper component that adds swipe gesture detection to its children
 *
 * Detects swipe gestures in all four directions with configurable threshold
 * Provides both general and direction-specific callbacks
 *
 * @param {SwipeHandlerProps} props - Component props
 * @returns {JSX.Element} Children wrapped with swipe detection
 *
 * @example
 * ```tsx
 * <SwipeHandler
 *   onSwipeLeft={() => navigate('next')}
 *   onSwipeRight={() => navigate('prev')}
 *   threshold={75}
 * >
 *   <ProspectProfile />
 * </SwipeHandler>
 * ```
 */
export const SwipeHandler: React.FC<SwipeHandlerProps> = ({
  children,
  onSwipe,
  onSwipeLeft,
  onSwipeRight,
  onSwipeUp,
  onSwipeDown,
  threshold = 50,
  enabled = true,
  className = ''
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const touchStartRef = useRef<{ x: number; y: number } | null>(null);
  const touchEndRef = useRef<{ x: number; y: number } | null>(null);

  useEffect(() => {
    if (!enabled || !containerRef.current) return;

    const element = containerRef.current;

    /**
     * Handle touch start event
     *
     * @param {TouchEvent} e - Touch event
     */
    const handleTouchStart = (e: TouchEvent) => {
      touchStartRef.current = {
        x: e.touches[0].clientX,
        y: e.touches[0].clientY
      };
    };

    /**
     * Handle touch move event
     *
     * @param {TouchEvent} e - Touch event
     */
    const handleTouchMove = (e: TouchEvent) => {
      touchEndRef.current = {
        x: e.touches[0].clientX,
        y: e.touches[0].clientY
      };
    };

    /**
     * Handle touch end event and detect swipe
     *
     * @param {TouchEvent} e - Touch event
     */
    const handleTouchEnd = (e: TouchEvent) => {
      if (!touchStartRef.current || !touchEndRef.current) return;

      const deltaX = touchEndRef.current.x - touchStartRef.current.x;
      const deltaY = touchEndRef.current.y - touchStartRef.current.y;
      const absX = Math.abs(deltaX);
      const absY = Math.abs(deltaY);

      // Determine if swipe threshold was met
      if (Math.max(absX, absY) < threshold) {
        return;
      }

      // Determine swipe direction
      let direction: SwipeDirection;

      if (absX > absY) {
        // Horizontal swipe
        direction = deltaX > 0 ? 'right' : 'left';
      } else {
        // Vertical swipe
        direction = deltaY > 0 ? 'down' : 'up';
      }

      // Call appropriate callbacks
      onSwipe?.(direction);

      switch (direction) {
        case 'left':
          onSwipeLeft?.();
          break;
        case 'right':
          onSwipeRight?.();
          break;
        case 'up':
          onSwipeUp?.();
          break;
        case 'down':
          onSwipeDown?.();
          break;
      }

      // Reset refs
      touchStartRef.current = null;
      touchEndRef.current = null;
    };

    // Add event listeners
    element.addEventListener('touchstart', handleTouchStart, { passive: true });
    element.addEventListener('touchmove', handleTouchMove, { passive: true });
    element.addEventListener('touchend', handleTouchEnd, { passive: true });

    // Cleanup
    return () => {
      element.removeEventListener('touchstart', handleTouchStart);
      element.removeEventListener('touchmove', handleTouchMove);
      element.removeEventListener('touchend', handleTouchEnd);
    };
  }, [enabled, threshold, onSwipe, onSwipeLeft, onSwipeRight, onSwipeUp, onSwipeDown]);

  return (
    <div ref={containerRef} className={className}>
      {children}
    </div>
  );
};

export default SwipeHandler;