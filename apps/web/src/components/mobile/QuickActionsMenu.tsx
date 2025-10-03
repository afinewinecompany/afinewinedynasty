/**
 * Quick actions menu for long-press interactions on mobile
 *
 * @component QuickActionsMenu
 * @since 1.0.0
 */

import React, { useState, useRef, useEffect, ReactNode } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

/**
 * Quick action item configuration
 *
 * @interface QuickAction
 */
export interface QuickAction {
  /** Unique identifier for the action */
  id: string;

  /** Display label for the action */
  label: string;

  /** Icon or emoji for the action */
  icon: string;

  /** Callback when action is selected */
  onClick: () => void;

  /** Whether action is destructive (shown in red) */
  destructive?: boolean;
}

/**
 * Props for QuickActionsMenu component
 *
 * @interface QuickActionsMenuProps
 */
interface QuickActionsMenuProps {
  /** Child element that triggers the menu on long press */
  children: ReactNode;

  /** Array of quick actions to display */
  actions: QuickAction[];

  /** Whether long press is enabled (default: true) */
  enabled?: boolean;

  /** Long press duration in ms (default: 500) */
  longPressDuration?: number;

  /** Enable haptic feedback on supported devices (default: true) */
  hapticFeedback?: boolean;

  /** Additional CSS classes */
  className?: string;
}

/**
 * Long-press activated quick action menu for mobile interactions
 *
 * Shows contextual menu with quick actions on long press
 * Provides haptic feedback and smooth animations
 *
 * @param {QuickActionsMenuProps} props - Component props
 * @returns {JSX.Element} Children with long-press menu functionality
 *
 * @example
 * ```tsx
 * <QuickActionsMenu
 *   actions={[
 *     { id: 'compare', label: 'Compare', icon: '⚖️', onClick: handleCompare },
 *     { id: 'share', label: 'Share', icon: '📤', onClick: handleShare },
 *     { id: 'delete', label: 'Delete', icon: '🗑️', onClick: handleDelete, destructive: true }
 *   ]}
 * >
 *   <ProspectCard prospect={prospect} />
 * </QuickActionsMenu>
 * ```
 */
export const QuickActionsMenu: React.FC<QuickActionsMenuProps> = ({
  children,
  actions,
  enabled = true,
  longPressDuration = 500,
  hapticFeedback = true,
  className = '',
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [menuPosition, setMenuPosition] = useState({ x: 0, y: 0 });
  const containerRef = useRef<HTMLDivElement>(null);
  const longPressTimerRef = useRef<NodeJS.Timeout>();
  const touchStartRef = useRef<{ x: number; y: number } | null>(null);

  /**
   * Trigger haptic feedback if available
   */
  const triggerHaptic = () => {
    if (hapticFeedback && 'vibrate' in navigator) {
      navigator.vibrate(10); // Short vibration
    }
  };

  /**
   * Handle touch start event
   */
  const handleTouchStart = (e: React.TouchEvent) => {
    if (!enabled) return;

    const touch = e.touches[0];
    touchStartRef.current = { x: touch.clientX, y: touch.clientY };

    // Start long press timer
    longPressTimerRef.current = setTimeout(() => {
      triggerHaptic();
      setMenuPosition({ x: touch.clientX, y: touch.clientY });
      setIsOpen(true);
    }, longPressDuration);
  };

  /**
   * Handle touch move event
   */
  const handleTouchMove = (e: React.TouchEvent) => {
    if (!touchStartRef.current) return;

    const touch = e.touches[0];
    const deltaX = Math.abs(touch.clientX - touchStartRef.current.x);
    const deltaY = Math.abs(touch.clientY - touchStartRef.current.y);

    // Cancel long press if user moves finger too far
    if (deltaX > 10 || deltaY > 10) {
      if (longPressTimerRef.current) {
        clearTimeout(longPressTimerRef.current);
      }
    }
  };

  /**
   * Handle touch end event
   */
  const handleTouchEnd = () => {
    if (longPressTimerRef.current) {
      clearTimeout(longPressTimerRef.current);
    }
    touchStartRef.current = null;
  };

  /**
   * Handle context menu (right-click on desktop)
   */
  const handleContextMenu = (e: React.MouseEvent) => {
    if (!enabled) return;

    e.preventDefault();
    setMenuPosition({ x: e.clientX, y: e.clientY });
    setIsOpen(true);
  };

  /**
   * Handle action selection
   */
  const handleAction = (action: QuickAction) => {
    action.onClick();
    setIsOpen(false);
  };

  /**
   * Close menu when clicking outside
   */
  useEffect(() => {
    if (!isOpen) return;

    const handleClickOutside = (e: MouseEvent | TouchEvent) => {
      const target = e.target as Node;
      if (containerRef.current && !containerRef.current.contains(target)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('touchstart', handleClickOutside);

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('touchstart', handleClickOutside);
    };
  }, [isOpen]);

  // Calculate menu position to keep it on screen
  const getMenuStyle = () => {
    const menuWidth = 200;
    const menuHeight = actions.length * 50 + 20;
    const padding = 10;

    let x = menuPosition.x;
    let y = menuPosition.y;

    // Adjust horizontal position
    if (x + menuWidth > window.innerWidth - padding) {
      x = window.innerWidth - menuWidth - padding;
    }
    if (x < padding) {
      x = padding;
    }

    // Adjust vertical position
    if (y + menuHeight > window.innerHeight - padding) {
      y = window.innerHeight - menuHeight - padding;
    }
    if (y < padding) {
      y = padding;
    }

    return {
      position: 'fixed' as const,
      left: `${x}px`,
      top: `${y}px`,
      zIndex: 1000,
    };
  };

  return (
    <div
      ref={containerRef}
      className={className}
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
      onContextMenu={handleContextMenu}
    >
      {children}

      {/* Quick Actions Menu */}
      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black bg-opacity-20 z-[999]"
            onClick={() => setIsOpen(false)}
          />

          {/* Menu */}
          <Card
            className="w-[200px] p-2 shadow-xl animate-in fade-in zoom-in-95 duration-200"
            style={getMenuStyle()}
          >
            <div className="flex flex-col gap-1">
              {actions.map((action) => (
                <Button
                  key={action.id}
                  variant="ghost"
                  size="sm"
                  className={`
                    justify-start min-h-[44px] px-3
                    ${action.destructive ? 'text-red-600 hover:text-red-700 hover:bg-red-50' : ''}
                  `}
                  onClick={() => handleAction(action)}
                >
                  <span className="mr-2 text-lg" role="img" aria-hidden="true">
                    {action.icon}
                  </span>
                  <span>{action.label}</span>
                </Button>
              ))}
            </div>
          </Card>
        </>
      )}
    </div>
  );
};

export default QuickActionsMenu;
