/**
 * Tests for gesture utilities
 */

import {
  GestureDetector,
  calculateSwipeVelocity,
  getSwipeOrientation,
  isTouchDevice,
  debounceTouchHandler
} from '@/lib/gestures';

describe('Gesture Utilities', () => {
  describe('calculateSwipeVelocity', () => {
    it('should calculate velocity correctly', () => {
      expect(calculateSwipeVelocity(150, 200)).toBe(0.75);
      expect(calculateSwipeVelocity(100, 50)).toBe(2);
      expect(calculateSwipeVelocity(0, 100)).toBe(0);
    });

    it('should handle zero time', () => {
      expect(calculateSwipeVelocity(100, 0)).toBe(0);
    });
  });

  describe('getSwipeOrientation', () => {
    it('should detect horizontal swipes', () => {
      expect(getSwipeOrientation(100, 30)).toBe('horizontal');
      expect(getSwipeOrientation(-100, 30)).toBe('horizontal');
      expect(getSwipeOrientation(50, -40)).toBe('horizontal');
    });

    it('should detect vertical swipes', () => {
      expect(getSwipeOrientation(30, 100)).toBe('vertical');
      expect(getSwipeOrientation(30, -100)).toBe('vertical');
      expect(getSwipeOrientation(-40, 50)).toBe('vertical');
    });

    it('should handle equal values', () => {
      expect(getSwipeOrientation(50, 50)).toBe('vertical');
    });
  });

  describe('isTouchDevice', () => {
    it('should detect touch support', () => {
      const originalOntouchstart = window.ontouchstart;
      const originalMaxTouchPoints = navigator.maxTouchPoints;

      // Test with ontouchstart
      Object.defineProperty(window, 'ontouchstart', {
        value: () => {},
        configurable: true
      });
      expect(isTouchDevice()).toBe(true);

      // Test with maxTouchPoints
      Object.defineProperty(window, 'ontouchstart', {
        value: undefined,
        configurable: true
      });
      Object.defineProperty(navigator, 'maxTouchPoints', {
        value: 2,
        configurable: true
      });
      expect(isTouchDevice()).toBe(true);

      // Test without touch support
      Object.defineProperty(navigator, 'maxTouchPoints', {
        value: 0,
        configurable: true
      });
      expect(isTouchDevice()).toBe(false);

      // Restore original values
      if (originalOntouchstart !== undefined) {
        Object.defineProperty(window, 'ontouchstart', {
          value: originalOntouchstart,
          configurable: true
        });
      }
      Object.defineProperty(navigator, 'maxTouchPoints', {
        value: originalMaxTouchPoints,
        configurable: true
      });
    });
  });

  describe('debounceTouchHandler', () => {
    jest.useFakeTimers();

    it('should debounce function calls', () => {
      const mockCallback = jest.fn();
      const debouncedFn = debounceTouchHandler(mockCallback, 300);

      // Call multiple times rapidly
      debouncedFn('test1');
      debouncedFn('test2');
      debouncedFn('test3');

      // Should not be called immediately
      expect(mockCallback).not.toHaveBeenCalled();

      // Fast-forward time
      jest.advanceTimersByTime(300);

      // Should be called once with last arguments
      expect(mockCallback).toHaveBeenCalledTimes(1);
      expect(mockCallback).toHaveBeenCalledWith('test3');
    });

    it('should handle immediate calls after delay', () => {
      const mockCallback = jest.fn();
      const debouncedFn = debounceTouchHandler(mockCallback, 300);

      debouncedFn('first');
      jest.advanceTimersByTime(400); // Wait longer than delay
      expect(mockCallback).toHaveBeenCalledWith('first');

      debouncedFn('second');
      expect(mockCallback).toHaveBeenCalledTimes(2); // Immediate call
      expect(mockCallback).toHaveBeenCalledWith('second');
    });

    afterEach(() => {
      jest.clearAllTimers();
    });
  });

  describe('GestureDetector', () => {
    let element: HTMLElement;
    let detector: GestureDetector;

    beforeEach(() => {
      element = document.createElement('div');
      document.body.appendChild(element);
    });

    afterEach(() => {
      if (detector) {
        detector.destroy();
      }
      document.body.removeChild(element);
    });

    it('should create gesture detector instance', () => {
      detector = new GestureDetector(element);
      expect(detector).toBeDefined();
    });

    it('should detect swipe gestures', (done) => {
      detector = new GestureDetector(element, {
        swipeThreshold: 50,
        swipeTimeout: 300
      });

      detector.on('swipe', (event) => {
        expect(event.type).toBe('swipe');
        expect(event.direction).toBe('right');
        expect(event.distance).toBeGreaterThan(50);
        done();
      });

      // Simulate swipe right
      const touchStart = new TouchEvent('touchstart', {
        touches: [{ clientX: 0, clientY: 50 } as Touch]
      });
      const touchEnd = new TouchEvent('touchend', {
        changedTouches: [{ clientX: 100, clientY: 50 } as Touch]
      });

      element.dispatchEvent(touchStart);
      setTimeout(() => {
        element.dispatchEvent(touchEnd);
      }, 100);
    });

    it('should detect long press', (done) => {
      jest.useFakeTimers();

      detector = new GestureDetector(element, {
        longPressDuration: 500
      });

      detector.on('longpress', (event) => {
        expect(event.type).toBe('longpress');
        done();
      });

      // Simulate long press
      const touchStart = new TouchEvent('touchstart', {
        touches: [{ clientX: 50, clientY: 50 } as Touch]
      });

      element.dispatchEvent(touchStart);
      jest.advanceTimersByTime(600);

      jest.useRealTimers();
    });

    it('should detect double tap', () => {
      detector = new GestureDetector(element, {
        doubleTapInterval: 300
      });

      const mockCallback = jest.fn();
      detector.on('doubletap', mockCallback);

      // Simulate double tap
      const touchStart = new TouchEvent('touchstart', {
        touches: [{ clientX: 50, clientY: 50 } as Touch]
      });
      const touchEnd = new TouchEvent('touchend', {
        changedTouches: [{ clientX: 50, clientY: 50 } as Touch]
      });

      // First tap
      element.dispatchEvent(touchStart);
      element.dispatchEvent(touchEnd);

      // Second tap within interval
      setTimeout(() => {
        element.dispatchEvent(touchStart);
        element.dispatchEvent(touchEnd);
        expect(mockCallback).toHaveBeenCalledWith(
          expect.objectContaining({ type: 'doubletap' })
        );
      }, 100);
    });

    it('should cancel long press on movement', () => {
      jest.useFakeTimers();

      detector = new GestureDetector(element, {
        longPressDuration: 500
      });

      const mockCallback = jest.fn();
      detector.on('longpress', mockCallback);

      // Start touch
      const touchStart = new TouchEvent('touchstart', {
        touches: [{ clientX: 50, clientY: 50 } as Touch]
      });
      element.dispatchEvent(touchStart);

      // Move finger (cancel long press)
      const touchMove = new TouchEvent('touchmove', {
        touches: [{ clientX: 80, clientY: 80 } as Touch]
      });
      element.dispatchEvent(touchMove);

      jest.advanceTimersByTime(600);

      expect(mockCallback).not.toHaveBeenCalled();

      jest.useRealTimers();
    });
  });
});