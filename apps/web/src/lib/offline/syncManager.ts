/**
 * @fileoverview Background sync manager for offline data synchronization
 *
 * Manages data synchronization between offline storage and server
 *
 * @module syncManager
 * @version 1.0.0
 * @since 1.0.0
 */

import { offlineStorage } from './offlineStorage';
import { getServiceWorkerManager } from './serviceWorker';

/**
 * Sync operation types
 *
 * @enum SyncType
 */
export enum SyncType {
  WATCHLIST_ADD = 'watchlist_add',
  WATCHLIST_REMOVE = 'watchlist_remove',
  COMPARISON_CREATE = 'comparison_create',
  PREFERENCE_UPDATE = 'preference_update',
  DATA_FETCH = 'data_fetch'
}

/**
 * Sync operation interface
 *
 * @interface SyncOperation
 */
interface SyncOperation {
  id: string;
  type: SyncType;
  data: any;
  timestamp: number;
  retries?: number;
}

/**
 * Sync manager configuration
 *
 * @interface SyncManagerConfig
 */
interface SyncManagerConfig {
  /** Enable auto sync on reconnect (default: true) */
  autoSync?: boolean;

  /** Maximum retry attempts (default: 3) */
  maxRetries?: number;

  /** Retry delay in ms (default: 1000) */
  retryDelay?: number;

  /** Batch size for sync operations (default: 10) */
  batchSize?: number;
}

/**
 * Background sync manager for handling offline operations
 *
 * @class SyncManager
 * @since 1.0.0
 *
 * @example
 * ```typescript
 * const syncManager = new SyncManager();
 * await syncManager.init();
 *
 * // Queue operation for sync
 * await syncManager.queueOperation(SyncType.WATCHLIST_ADD, { prospectId: '123' });
 *
 * // Manual sync
 * await syncManager.syncAll();
 * ```
 */
export class SyncManager {
  private config: Required<SyncManagerConfig>;
  private isSyncing: boolean = false;
  private syncQueue: SyncOperation[] = [];

  /**
   * Create sync manager instance
   *
   * @param config - Configuration options
   */
  constructor(config: SyncManagerConfig = {}) {
    this.config = {
      autoSync: config.autoSync ?? true,
      maxRetries: config.maxRetries ?? 3,
      retryDelay: config.retryDelay ?? 1000,
      batchSize: config.batchSize ?? 10
    };
  }

  /**
   * Initialize sync manager
   *
   * @returns Promise resolving when initialized
   */
  async init(): Promise<void> {
    // Load pending operations from storage
    await this.loadPendingOperations();

    // Setup online/offline listeners
    if (this.config.autoSync) {
      this.setupAutoSync();
    }
  }

  /**
   * Setup automatic sync on reconnect
   */
  private setupAutoSync(): void {
    window.addEventListener('online', () => {
      console.log('[SyncManager] Connection restored, starting sync');
      this.syncAll();
    });

    // Sync on visibility change (tab becomes visible)
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden && navigator.onLine) {
        this.syncAll();
      }
    });
  }

  /**
   * Load pending operations from offline storage
   */
  private async loadPendingOperations(): Promise<void> {
    try {
      const pending = await offlineStorage.getPendingSync();
      this.syncQueue = pending.map(item => ({
        id: item.id,
        type: item.type as SyncType,
        data: item.data,
        timestamp: item.data.timestamp || Date.now(),
        retries: 0
      }));

      console.log(`[SyncManager] Loaded ${this.syncQueue.length} pending operations`);
    } catch (error) {
      console.error('[SyncManager] Failed to load pending operations:', error);
    }
  }

  /**
   * Queue operation for synchronization
   *
   * @param type - Operation type
   * @param data - Operation data
   * @returns Promise resolving when queued
   */
  async queueOperation(type: SyncType, data: any): Promise<void> {
    const operation: SyncOperation = {
      id: `${type}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      type,
      data,
      timestamp: Date.now(),
      retries: 0
    };

    // Add to queue
    this.syncQueue.push(operation);

    // Save to offline storage
    await offlineStorage.getPendingSync(); // Ensure DB is open
    // Note: This is a simplified version - actual implementation would save to pendingSync store

    // Attempt immediate sync if online
    if (navigator.onLine) {
      this.syncOperation(operation);
    }
  }

  /**
   * Sync all pending operations
   *
   * @returns Promise resolving when sync complete
   */
  async syncAll(): Promise<void> {
    if (this.isSyncing || !navigator.onLine) {
      return;
    }

    this.isSyncing = true;

    try {
      // Request background sync if available
      const swManager = getServiceWorkerManager();
      await swManager.requestBackgroundSync('sync-data');

      // Process operations in batches
      while (this.syncQueue.length > 0) {
        const batch = this.syncQueue.splice(0, this.config.batchSize);
        await this.syncBatch(batch);
      }

      console.log('[SyncManager] All operations synced successfully');
    } catch (error) {
      console.error('[SyncManager] Sync failed:', error);
    } finally {
      this.isSyncing = false;
    }
  }

  /**
   * Sync a batch of operations
   *
   * @param batch - Operations to sync
   * @returns Promise resolving when batch synced
   */
  private async syncBatch(batch: SyncOperation[]): Promise<void> {
    const promises = batch.map(op => this.syncOperation(op));
    const results = await Promise.allSettled(promises);

    // Handle failed operations
    results.forEach((result, index) => {
      if (result.status === 'rejected') {
        const operation = batch[index];
        this.handleSyncFailure(operation);
      }
    });
  }

  /**
   * Sync single operation
   *
   * @param operation - Operation to sync
   * @returns Promise resolving when synced
   */
  private async syncOperation(operation: SyncOperation): Promise<void> {
    try {
      switch (operation.type) {
        case SyncType.WATCHLIST_ADD:
          await this.syncWatchlistAdd(operation.data);
          break;
        case SyncType.WATCHLIST_REMOVE:
          await this.syncWatchlistRemove(operation.data);
          break;
        case SyncType.COMPARISON_CREATE:
          await this.syncComparisonCreate(operation.data);
          break;
        case SyncType.PREFERENCE_UPDATE:
          await this.syncPreferenceUpdate(operation.data);
          break;
        case SyncType.DATA_FETCH:
          await this.syncDataFetch(operation.data);
          break;
        default:
          console.warn('[SyncManager] Unknown operation type:', operation.type);
      }

      // Remove from pending sync
      await offlineStorage.clearPendingSync([operation.id]);
    } catch (error) {
      throw error; // Re-throw for batch handler
    }
  }

  /**
   * Handle sync failure
   *
   * @param operation - Failed operation
   */
  private async handleSyncFailure(operation: SyncOperation): Promise<void> {
    operation.retries = (operation.retries || 0) + 1;

    if (operation.retries < this.config.maxRetries) {
      // Re-queue for retry
      setTimeout(() => {
        this.syncQueue.push(operation);
        if (navigator.onLine) {
          this.syncOperation(operation);
        }
      }, this.config.retryDelay * operation.retries);
    } else {
      console.error('[SyncManager] Operation failed after max retries:', operation);
      // Could notify user of permanent failure
    }
  }

  /**
   * Sync watchlist addition
   */
  private async syncWatchlistAdd(data: any): Promise<void> {
    const response = await fetch('/api/watchlist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prospectId: data.prospectId })
    });

    if (!response.ok) {
      throw new Error(`Watchlist add failed: ${response.status}`);
    }
  }

  /**
   * Sync watchlist removal
   */
  private async syncWatchlistRemove(data: any): Promise<void> {
    const response = await fetch(`/api/watchlist/${data.prospectId}`, {
      method: 'DELETE'
    });

    if (!response.ok) {
      throw new Error(`Watchlist remove failed: ${response.status}`);
    }
  }

  /**
   * Sync comparison creation
   */
  private async syncComparisonCreate(data: any): Promise<void> {
    const response = await fetch('/api/comparisons', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prospectIds: data.prospectIds })
    });

    if (!response.ok) {
      throw new Error(`Comparison create failed: ${response.status}`);
    }
  }

  /**
   * Sync preference update
   */
  private async syncPreferenceUpdate(data: any): Promise<void> {
    const response = await fetch('/api/users/preferences', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data.preferences)
    });

    if (!response.ok) {
      throw new Error(`Preference update failed: ${response.status}`);
    }
  }

  /**
   * Sync data fetch
   */
  private async syncDataFetch(data: any): Promise<void> {
    // Fetch latest data and update cache
    const response = await fetch(data.url);

    if (!response.ok) {
      throw new Error(`Data fetch failed: ${response.status}`);
    }

    const responseData = await response.json();

    // Update offline storage based on data type
    if (data.type === 'rankings') {
      await offlineStorage.saveRankings(responseData.items);
    } else if (data.type === 'prospect') {
      await offlineStorage.saveProspect(responseData);
    }
  }

  /**
   * Get sync status
   *
   * @returns Sync status information
   */
  getStatus(): {
    isSyncing: boolean;
    pendingCount: number;
    isOnline: boolean;
  } {
    return {
      isSyncing: this.isSyncing,
      pendingCount: this.syncQueue.length,
      isOnline: navigator.onLine
    };
  }

  /**
   * Clear all pending operations
   *
   * @returns Promise resolving when cleared
   */
  async clearPending(): Promise<void> {
    this.syncQueue = [];
    const pending = await offlineStorage.getPendingSync();
    await offlineStorage.clearPendingSync(pending.map(p => p.id));
  }
}

// Create singleton instance
export const syncManager = new SyncManager();