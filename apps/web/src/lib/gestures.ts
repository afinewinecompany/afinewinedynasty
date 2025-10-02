/**
 * @fileoverview Touch gesture utilities for mobile interactions
 *
 * This module provides utilities for detecting and handling touch gestures
 * including swipes, long press, double tap, and pinch zoom
 *
 * @module gestures
 * @version 1.0.0
 * @since 1.0.0
 */

/**
 * Gesture configuration options
 *
 * @interface GestureConfig
 */
export interface GestureConfig {
  /** Minimum distance for swipe detection (default: 50px) */
  swipeThreshold?: number;

  /** Maximum time for swipe gesture (default: 300ms) */
  swipeTimeout?: number;

  /** Long press duration (default: 500ms) */
  longPressDuration?: number;

  /** Double tap interval (default: 300ms) */
  doubleTapInterval?: number;

  /** Enable haptic feedback (default: true) */
  hapticFeedback?: boolean;
}

/**
 * Touch point information
 *
 * @interface TouchPoint
 */
export interface TouchPoint {
  x: number;
  y: number;
  timestamp: number;
}

/**
 * Gesture event data
 *
 * @interface GestureEvent
 */
export interface GestureEvent {
  type: 'swipe' | 'longpress' | 'doubletap' | 'pinch';
  direction?: 'left' | 'right' | 'up' | 'down';
  distance?: number;
  velocity?: number;
  scale?: number;
}

/**
 * Gesture detector class for handling complex touch interactions
 *
 * @class GestureDetector
 * @since 1.0.0
 *
 * @example
 * ```typescript
 * const detector = new GestureDetector(element, {
 *   swipeThreshold: 75,
 *   longPressDuration: 600
 * });
 *
 * detector.on('swipe', (event) => {
 *   console.log(`Swiped ${event.direction}`);
 * });
 * ```
 */
export class GestureDetector {
  private element: HTMLElement;
  private config: Required<GestureConfig>;
  private listeners: Map<string, Array<(event: GestureEvent) => void>>;
  private touchStart: TouchPoint | null = null;
  private lastTap: number = 0;
  private longPressTimer: NodeJS.Timeout | null = null;

  /**
   * Create a new gesture detector
   *
   * @param element - DOM element to attach gesture detection to
   * @param config - Configuration options
   */
  constructor(element: HTMLElement, config: GestureConfig = {}) {
    this.element = element;
    this.config = {
      swipeThreshold: config.swipeThreshold ?? 50,
      swipeTimeout: config.swipeTimeout ?? 300,
      longPressDuration: config.longPressDuration ?? 500,
      doubleTapInterval: config.doubleTapInterval ?? 300,
      hapticFeedback: config.hapticFeedback ?? true
    };
    this.listeners = new Map();

    this.attachListeners();
  }

  /**
   * Attach event listeners to element
   */
  private attachListeners(): void {
    this.element.addEventListener('touchstart', this.handleTouchStart, { passive: true });
    this.element.addEventListener('touchmove', this.handleTouchMove, { passive: true });
    this.element.addEventListener('touchend', this.handleTouchEnd, { passive: true });
  }

  /**
   * Handle touch start event
   */
  private handleTouchStart = (e: TouchEvent): void => {
    const touch = e.touches[0];
    this.touchStart = {
      x: touch.clientX,
      y: touch.clientY,
      timestamp: Date.now()
    };

    // Start long press detection
    this.longPressTimer = setTimeout(() => {
      this.triggerHaptic();
      this.emit('longpress', { type: 'longpress' });
    }, this.config.longPressDuration);
  };

  /**
   * Handle touch move event
   */
  private handleTouchMove = (e: TouchEvent): void => {
    if (!this.touchStart) return;

    const touch = e.touches[0];
    const deltaX = Math.abs(touch.clientX - this.touchStart.x);
    const deltaY = Math.abs(touch.clientY - this.touchStart.y);

    // Cancel long press if movement detected
    if ((deltaX > 10 || deltaY > 10) && this.longPressTimer) {
      clearTimeout(this.longPressTimer);
      this.longPressTimer = null;
    }
  };

  /**
   * Handle touch end event
   */
  private handleTouchEnd = (e: TouchEvent): void => {
    if (!this.touchStart) return;

    // Clear long press timer
    if (this.longPressTimer) {
      clearTimeout(this.longPressTimer);
      this.longPressTimer = null;
    }

    const touchEnd = {
      x: e.changedTouches[0].clientX,
      y: e.changedTouches[0].clientY,
      timestamp: Date.now()
    };

    const deltaX = touchEnd.x - this.touchStart.x;
    const deltaY = touchEnd.y - this.touchStart.y;
    const deltaTime = touchEnd.timestamp - this.touchStart.timestamp;
    const distance = Math.sqrt(deltaX * deltaX + deltaY * deltaY);

    // Check for double tap
    if (distance < 30 && deltaTime < 200) {
      const tapDelta = touchEnd.timestamp - this.lastTap;
      if (tapDelta < this.config.doubleTapInterval) {
        this.triggerHaptic();
        this.emit('doubletap', { type: 'doubletap' });
        this.lastTap = 0;
      } else {
        this.lastTap = touchEnd.timestamp;
      }
    }

    // Check for swipe
    if (distance >= this.config.swipeThreshold && deltaTime <= this.config.swipeTimeout) {
      const absX = Math.abs(deltaX);
      const absY = Math.abs(deltaY);
      const velocity = distance / deltaTime;

      let direction: 'left' | 'right' | 'up' | 'down';
      if (absX > absY) {
        direction = deltaX > 0 ? 'right' : 'left';
      } else {
        direction = deltaY > 0 ? 'down' : 'up';
      }

      this.emit('swipe', {
        type: 'swipe',
        direction,
        distance,
        velocity
      });
    }

    this.touchStart = null;
  };

  /**
   * Trigger haptic feedback if available
   */
  private triggerHaptic(): void {
    if (this.config.hapticFeedback && 'vibrate' in navigator) {
      navigator.vibrate(10);
    }
  }

  /**
   * Register event listener
   *
   * @param event - Event type to listen for
   * @param callback - Callback function
   */
  on(event: string, callback: (event: GestureEvent) => void): void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event)!.push(callback);
  }

  /**
   * Emit event to listeners
   *
   * @param event - Event type
   * @param data - Event data
   */
  private emit(event: string, data: GestureEvent): void {
    const callbacks = this.listeners.get(event);
    if (callbacks) {
      callbacks.forEach(callback => callback(data));
    }
  }

  /**
   * Remove all event listeners
   */
  destroy(): void {
    this.element.removeEventListener('touchstart', this.handleTouchStart);
    this.element.removeEventListener('touchmove', this.handleTouchMove);
    this.element.removeEventListener('touchend', this.handleTouchEnd);

    if (this.longPressTimer) {
      clearTimeout(this.longPressTimer);
    }

    this.listeners.clear();
  }
}

/**
 * Calculate swipe velocity in pixels per millisecond
 *
 * @param distance - Distance traveled in pixels
 * @param time - Time taken in milliseconds
 * @returns Velocity in px/ms
 *
 * @example
 * ```typescript
 * const velocity = calculateSwipeVelocity(150, 200);
 * console.log(velocity); // 0.75
 * ```
 */
export function calculateSwipeVelocity(distance: number, time: number): number {
  return time > 0 ? distance / time : 0;
}

/**
 * Determine if a touch movement is primarily horizontal or vertical
 *
 * @param deltaX - Horizontal movement
 * @param deltaY - Vertical movement
 * @returns 'horizontal' or 'vertical'
 *
 * @example
 * ```typescript
 * const direction = getSwipeDirection(100, 30);
 * console.log(direction); // 'horizontal'
 * ```
 */
export function getSwipeOrientation(deltaX: number, deltaY: number): 'horizontal' | 'vertical' {
  return Math.abs(deltaX) > Math.abs(deltaY) ? 'horizontal' : 'vertical';
}

/**
 * Check if device supports touch events
 *
 * @returns True if touch is supported
 *
 * @example
 * ```typescript
 * if (isTouchDevice()) {
 *   // Enable touch interactions
 * }
 * ```
 */
export function isTouchDevice(): boolean {
  return 'ontouchstart' in window || navigator.maxTouchPoints > 0;
}

/**
 * Check if device supports haptic feedback
 *
 * @returns True if haptic feedback is supported
 *
 * @example
 * ```typescript
 * if (supportsHaptic()) {
 *   navigator.vibrate(10);
 * }
 * ```
 */
export function supportsHaptic(): boolean {
  return 'vibrate' in navigator;
}

/**
 * Create a debounced touch handler to prevent rapid firing
 *
 * @param callback - Function to debounce
 * @param delay - Delay in milliseconds
 * @returns Debounced function
 *
 * @example
 * ```typescript
 * const debouncedHandler = debounceTouchHandler(
 *   () => console.log('Touch handled'),
 *   300
 * );
 * ```
 */
export function debounceTouchHandler<T extends (...args: any[]) => void>(
  callback: T,
  delay: number
): T {
  let timeoutId: NodeJS.Timeout | null = null;
  let lastCallTime = 0;

  return ((...args: Parameters<T>) => {
    const now = Date.now();
    const timeSinceLastCall = now - lastCallTime;

    if (timeoutId) {
      clearTimeout(timeoutId);
    }

    if (timeSinceLastCall >= delay) {
      callback(...args);
      lastCallTime = now;
    } else {
      timeoutId = setTimeout(() => {
        callback(...args);
        lastCallTime = Date.now();
      }, delay - timeSinceLastCall);
    }
  }) as T;
}