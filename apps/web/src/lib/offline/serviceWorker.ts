/**
 * @fileoverview Service worker registration and management
 *
 * Handles service worker lifecycle, updates, and messaging
 *
 * @module serviceWorker
 * @version 1.0.0
 * @since 1.0.0
 */

/**
 * Service worker registration configuration
 *
 * @interface ServiceWorkerConfig
 */
interface ServiceWorkerConfig {
  /** Service worker file path */
  swPath?: string;

  /** Enable auto updates (default: true) */
  autoUpdate?: boolean;

  /** Update check interval in ms (default: 1 hour) */
  updateInterval?: number;

  /** Callback when update is available */
  onUpdateAvailable?: (registration: ServiceWorkerRegistration) => void;

  /** Callback when update is installed */
  onUpdateInstalled?: () => void;
}

/**
 * Service worker manager class
 *
 * @class ServiceWorkerManager
 * @since 1.0.0
 *
 * @example
 * ```typescript
 * const swManager = new ServiceWorkerManager({
 *   onUpdateAvailable: () => console.log('Update available!')
 * });
 *
 * await swManager.register();
 * ```
 */
export class ServiceWorkerManager {
  private registration: ServiceWorkerRegistration | null = null;
  private config: Required<ServiceWorkerConfig>;
  private updateCheckInterval: NodeJS.Timeout | null = null;

  /**
   * Create service worker manager instance
   *
   * @param config - Configuration options
   */
  constructor(config: ServiceWorkerConfig = {}) {
    this.config = {
      swPath: config.swPath || '/sw.js',
      autoUpdate: config.autoUpdate ?? true,
      updateInterval: config.updateInterval || 60 * 60 * 1000, // 1 hour
      onUpdateAvailable: config.onUpdateAvailable || (() => {}),
      onUpdateInstalled: config.onUpdateInstalled || (() => {})
    };
  }

  /**
   * Register service worker
   *
   * @returns Promise resolving to registration
   *
   * @throws {Error} If service workers are not supported
   */
  async register(): Promise<ServiceWorkerRegistration> {
    if (!('serviceWorker' in navigator)) {
      throw new Error('Service Workers are not supported in this browser');
    }

    try {
      // Register service worker
      this.registration = await navigator.serviceWorker.register(
        this.config.swPath,
        { scope: '/' }
      );

      console.log('[ServiceWorker] Registered successfully');

      // Setup event listeners
      this.setupEventListeners();

      // Setup auto update if enabled
      if (this.config.autoUpdate) {
        this.startAutoUpdate();
      }

      // Check for updates immediately
      this.checkForUpdate();

      return this.registration;
    } catch (error) {
      console.error('[ServiceWorker] Registration failed:', error);
      throw error;
    }
  }

  /**
   * Setup service worker event listeners
   */
  private setupEventListeners(): void {
    if (!this.registration) return;

    // Listen for update found
    this.registration.addEventListener('updatefound', () => {
      const newWorker = this.registration!.installing;
      if (!newWorker) return;

      newWorker.addEventListener('statechange', () => {
        if (newWorker.state === 'installed') {
          if (navigator.serviceWorker.controller) {
            // New service worker available
            console.log('[ServiceWorker] Update available');
            this.config.onUpdateAvailable(this.registration!);
          } else {
            // Initial install
            console.log('[ServiceWorker] Content cached for offline');
            this.config.onUpdateInstalled();
          }
        }
      });
    });

    // Listen for controller change
    navigator.serviceWorker.addEventListener('controllerchange', () => {
      console.log('[ServiceWorker] Controller changed');
      window.location.reload();
    });

    // Listen for messages from service worker
    navigator.serviceWorker.addEventListener('message', this.handleMessage);
  }

  /**
   * Handle messages from service worker
   */
  private handleMessage = (event: MessageEvent): void => {
    console.log('[ServiceWorker] Message received:', event.data);

    switch (event.data.type) {
      case 'SYNC_START':
        this.onSyncStart();
        break;
      case 'SYNC_COMPLETE':
        this.onSyncComplete();
        break;
      case 'CACHE_UPDATED':
        this.onCacheUpdated(event.data.urls);
        break;
      default:
        console.log('[ServiceWorker] Unknown message type:', event.data.type);
    }
  };

  /**
   * Start automatic update checking
   */
  private startAutoUpdate(): void {
    this.updateCheckInterval = setInterval(() => {
      this.checkForUpdate();
    }, this.config.updateInterval);
  }

  /**
   * Check for service worker updates
   *
   * @returns Promise resolving when check is complete
   */
  async checkForUpdate(): Promise<void> {
    if (!this.registration) return;

    try {
      await this.registration.update();
      console.log('[ServiceWorker] Update check complete');
    } catch (error) {
      console.error('[ServiceWorker] Update check failed:', error);
    }
  }

  /**
   * Skip waiting and activate new service worker
   *
   * @returns Promise resolving when activated
   */
  async skipWaiting(): Promise<void> {
    if (!this.registration?.waiting) {
      console.log('[ServiceWorker] No waiting worker');
      return;
    }

    // Send skip waiting message to service worker
    this.registration.waiting.postMessage({ type: 'SKIP_WAITING' });

    // Wait for controller to change
    return new Promise((resolve) => {
      const onControllerChange = () => {
        navigator.serviceWorker.removeEventListener(
          'controllerchange',
          onControllerChange
        );
        resolve();
      };

      navigator.serviceWorker.addEventListener(
        'controllerchange',
        onControllerChange
      );
    });
  }

  /**
   * Unregister service worker
   *
   * @returns Promise resolving when unregistered
   */
  async unregister(): Promise<boolean> {
    if (!this.registration) return false;

    // Clear update interval
    if (this.updateCheckInterval) {
      clearInterval(this.updateCheckInterval);
    }

    // Remove event listeners
    navigator.serviceWorker.removeEventListener('message', this.handleMessage);

    // Unregister service worker
    const success = await this.registration.unregister();
    console.log('[ServiceWorker] Unregistered:', success);

    this.registration = null;
    return success;
  }

  /**
   * Clear all caches
   *
   * @returns Promise resolving when cleared
   */
  async clearCaches(): Promise<void> {
    if (!('caches' in window)) return;

    const cacheNames = await caches.keys();
    await Promise.all(
      cacheNames.map(cacheName => caches.delete(cacheName))
    );

    console.log('[ServiceWorker] All caches cleared');
  }

  /**
   * Send message to service worker
   *
   * @param message - Message to send
   */
  postMessage(message: any): void {
    if (!this.registration?.active) {
      console.warn('[ServiceWorker] No active worker');
      return;
    }

    this.registration.active.postMessage(message);
  }

  /**
   * Cache specific URLs
   *
   * @param urls - URLs to cache
   * @returns Promise resolving when cached
   */
  async cacheUrls(urls: string[]): Promise<void> {
    this.postMessage({
      type: 'CACHE_URLS',
      urls
    });
  }

  /**
   * Request background sync
   *
   * @param tag - Sync tag
   * @returns Promise resolving when registered
   */
  async requestBackgroundSync(tag: string): Promise<void> {
    if (!this.registration) {
      throw new Error('Service worker not registered');
    }

    if (!('sync' in this.registration)) {
      console.warn('[ServiceWorker] Background sync not supported');
      return;
    }

    await this.registration.sync.register(tag);
    console.log('[ServiceWorker] Background sync registered:', tag);
  }

  /**
   * Get registration status
   *
   * @returns Registration status
   */
  getStatus(): {
    registered: boolean;
    active: boolean;
    waiting: boolean;
    installing: boolean;
  } {
    return {
      registered: !!this.registration,
      active: !!this.registration?.active,
      waiting: !!this.registration?.waiting,
      installing: !!this.registration?.installing
    };
  }

  // Event handlers
  private onSyncStart(): void {
    console.log('[ServiceWorker] Sync started');
  }

  private onSyncComplete(): void {
    console.log('[ServiceWorker] Sync complete');
  }

  private onCacheUpdated(urls: string[]): void {
    console.log('[ServiceWorker] Cache updated:', urls);
  }
}

// Create singleton instance
let serviceWorkerManagerInstance: ServiceWorkerManager | null = null;

/**
 * Get or create service worker manager instance
 *
 * @param config - Configuration options
 * @returns Service worker manager instance
 */
export function getServiceWorkerManager(
  config?: ServiceWorkerConfig
): ServiceWorkerManager {
  if (!serviceWorkerManagerInstance) {
    serviceWorkerManagerInstance = new ServiceWorkerManager(config);
  }
  return serviceWorkerManagerInstance;
}

/**
 * Register service worker with default config
 *
 * @returns Promise resolving to registration
 */
export async function registerServiceWorker(): Promise<ServiceWorkerRegistration | null> {
  if (typeof window === 'undefined') return null;

  const manager = getServiceWorkerManager({
    onUpdateAvailable: (registration) => {
      // Show update notification to user
      if (confirm('A new version is available. Update now?')) {
        manager.skipWaiting().then(() => {
          window.location.reload();
        });
      }
    }
  });

  try {
    return await manager.register();
  } catch (error) {
    console.error('Failed to register service worker:', error);
    return null;
  }
}