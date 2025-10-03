/**
 * @fileoverview Offline storage utilities using IndexedDB
 *
 * Provides local storage for prospects, rankings, and user data
 * Enables offline functionality and data persistence
 *
 * @module offlineStorage
 * @version 1.0.0
 * @since 1.0.0
 */

import type { ProspectProfile, ProspectRanking } from '@/types/prospect';

const DB_NAME = 'AFWDOfflineDB';
const DB_VERSION = 1;

/**
 * IndexedDB store configurations
 *
 * @interface StoreConfig
 */
interface StoreConfig {
  name: string;
  keyPath: string;
  indexes?: Array<{
    name: string;
    keyPath: string;
    unique?: boolean;
  }>;
}

const STORES: Record<string, StoreConfig> = {
  prospects: {
    name: 'prospects',
    keyPath: 'id',
    indexes: [
      { name: 'by_rank', keyPath: 'rank' },
      { name: 'by_updated', keyPath: 'updatedAt' },
    ],
  },
  rankings: {
    name: 'rankings',
    keyPath: 'timestamp',
    indexes: [{ name: 'by_position', keyPath: 'position' }],
  },
  watchlist: {
    name: 'watchlist',
    keyPath: 'prospectId',
    indexes: [{ name: 'by_added', keyPath: 'addedAt' }],
  },
  comparisons: {
    name: 'comparisons',
    keyPath: 'id',
    indexes: [{ name: 'by_created', keyPath: 'createdAt' }],
  },
  pendingSync: {
    name: 'pendingSync',
    keyPath: 'id',
    indexes: [
      { name: 'by_type', keyPath: 'type' },
      { name: 'by_timestamp', keyPath: 'timestamp' },
    ],
  },
};

/**
 * Offline storage manager for IndexedDB operations
 *
 * @class OfflineStorage
 * @since 1.0.0
 *
 * @example
 * ```typescript
 * const storage = new OfflineStorage();
 * await storage.init();
 * await storage.saveProspect(prospectData);
 * ```
 */
export class OfflineStorage {
  private db: IDBDatabase | null = null;

  /**
   * Initialize IndexedDB connection
   *
   * @returns Promise resolving when database is ready
   *
   * @throws {Error} If IndexedDB is not supported
   */
  async init(): Promise<void> {
    if (!('indexedDB' in window)) {
      throw new Error('IndexedDB is not supported in this browser');
    }

    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);

      request.onerror = () => reject(new Error('Failed to open IndexedDB'));

      request.onsuccess = () => {
        this.db = request.result;
        resolve();
      };

      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;

        // Create object stores
        Object.values(STORES).forEach((store) => {
          if (!db.objectStoreNames.contains(store.name)) {
            const objectStore = db.createObjectStore(store.name, {
              keyPath: store.keyPath,
            });

            // Create indexes
            store.indexes?.forEach((index) => {
              objectStore.createIndex(index.name, index.keyPath, {
                unique: index.unique || false,
              });
            });
          }
        });
      };
    });
  }

  /**
   * Save prospect data for offline access
   *
   * @param prospect - Prospect data to save
   * @returns Promise resolving when saved
   *
   * @example
   * ```typescript
   * await storage.saveProspect({
   *   id: '123',
   *   name: 'John Doe',
   *   rank: 5
   * });
   * ```
   */
  async saveProspect(prospect: ProspectProfile): Promise<void> {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(['prospects'], 'readwrite');
      const store = transaction.objectStore('prospects');

      const prospectWithTimestamp = {
        ...prospect,
        updatedAt: Date.now(),
      };

      const request = store.put(prospectWithTimestamp);

      request.onsuccess = () => resolve();
      request.onerror = () => reject(new Error('Failed to save prospect'));
    });
  }

  /**
   * Get prospect by ID
   *
   * @param id - Prospect ID
   * @returns Promise resolving to prospect data or null
   */
  async getProspect(id: string): Promise<ProspectProfile | null> {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(['prospects'], 'readonly');
      const store = transaction.objectStore('prospects');
      const request = store.get(id);

      request.onsuccess = () => resolve(request.result || null);
      request.onerror = () => reject(new Error('Failed to get prospect'));
    });
  }

  /**
   * Save rankings data for offline access
   *
   * @param rankings - Array of prospect rankings
   * @returns Promise resolving when saved
   */
  async saveRankings(rankings: ProspectRanking[]): Promise<void> {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(['rankings'], 'readwrite');
      const store = transaction.objectStore('rankings');

      const rankingData = {
        timestamp: Date.now(),
        rankings,
        count: rankings.length,
      };

      const request = store.put(rankingData);

      request.onsuccess = () => resolve();
      request.onerror = () => reject(new Error('Failed to save rankings'));
    });
  }

  /**
   * Get latest cached rankings
   *
   * @param limit - Maximum number of prospects to return
   * @returns Promise resolving to rankings array
   */
  async getRankings(limit: number = 100): Promise<ProspectRanking[]> {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(['rankings'], 'readonly');
      const store = transaction.objectStore('rankings');

      // Get most recent rankings
      const request = store.openCursor(null, 'prev');

      request.onsuccess = () => {
        const cursor = request.result;
        if (cursor) {
          const data = cursor.value;
          resolve(data.rankings.slice(0, limit));
        } else {
          resolve([]);
        }
      };

      request.onerror = () => reject(new Error('Failed to get rankings'));
    });
  }

  /**
   * Add prospect to watchlist
   *
   * @param prospectId - ID of prospect to watch
   * @returns Promise resolving when added
   */
  async addToWatchlist(prospectId: string): Promise<void> {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(
        ['watchlist', 'pendingSync'],
        'readwrite'
      );
      const watchlistStore = transaction.objectStore('watchlist');
      const syncStore = transaction.objectStore('pendingSync');

      // Add to watchlist
      watchlistStore.put({
        prospectId,
        addedAt: Date.now(),
      });

      // Add to pending sync
      syncStore.put({
        id: `watchlist_add_${prospectId}_${Date.now()}`,
        type: 'watchlist_add',
        prospectId,
        timestamp: Date.now(),
      });

      transaction.oncomplete = () => resolve();
      transaction.onerror = () =>
        reject(new Error('Failed to add to watchlist'));
    });
  }

  /**
   * Remove prospect from watchlist
   *
   * @param prospectId - ID of prospect to remove
   * @returns Promise resolving when removed
   */
  async removeFromWatchlist(prospectId: string): Promise<void> {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(
        ['watchlist', 'pendingSync'],
        'readwrite'
      );
      const watchlistStore = transaction.objectStore('watchlist');
      const syncStore = transaction.objectStore('pendingSync');

      // Remove from watchlist
      watchlistStore.delete(prospectId);

      // Add to pending sync
      syncStore.put({
        id: `watchlist_remove_${prospectId}_${Date.now()}`,
        type: 'watchlist_remove',
        prospectId,
        timestamp: Date.now(),
      });

      transaction.oncomplete = () => resolve();
      transaction.onerror = () =>
        reject(new Error('Failed to remove from watchlist'));
    });
  }

  /**
   * Get watchlist prospect IDs
   *
   * @returns Promise resolving to array of prospect IDs
   */
  async getWatchlist(): Promise<string[]> {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(['watchlist'], 'readonly');
      const store = transaction.objectStore('watchlist');
      const request = store.getAll();

      request.onsuccess = () => {
        const items = request.result || [];
        resolve(items.map((item) => item.prospectId));
      };

      request.onerror = () => reject(new Error('Failed to get watchlist'));
    });
  }

  /**
   * Save comparison data
   *
   * @param comparisonId - Unique comparison ID
   * @param prospectIds - Array of prospect IDs being compared
   * @returns Promise resolving when saved
   */
  async saveComparison(
    comparisonId: string,
    prospectIds: string[]
  ): Promise<void> {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(['comparisons'], 'readwrite');
      const store = transaction.objectStore('comparisons');

      store.put({
        id: comparisonId,
        prospectIds,
        createdAt: Date.now(),
      });

      transaction.oncomplete = () => resolve();
      transaction.onerror = () =>
        reject(new Error('Failed to save comparison'));
    });
  }

  /**
   * Get recent comparisons
   *
   * @param limit - Maximum number to return
   * @returns Promise resolving to comparison data
   */
  async getRecentComparisons(
    limit: number = 5
  ): Promise<Array<{ id: string; prospectIds: string[] }>> {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(['comparisons'], 'readonly');
      const store = transaction.objectStore('comparisons');
      const index = store.index('by_created');

      const comparisons: Array<{ id: string; prospectIds: string[] }> = [];
      const request = index.openCursor(null, 'prev');

      request.onsuccess = () => {
        const cursor = request.result;
        if (cursor && comparisons.length < limit) {
          comparisons.push({
            id: cursor.value.id,
            prospectIds: cursor.value.prospectIds,
          });
          cursor.continue();
        } else {
          resolve(comparisons);
        }
      };

      request.onerror = () => reject(new Error('Failed to get comparisons'));
    });
  }

  /**
   * Get pending sync operations
   *
   * @returns Promise resolving to array of pending operations
   */
  async getPendingSync(): Promise<
    Array<{ id: string; type: string; data: any }>
  > {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(['pendingSync'], 'readonly');
      const store = transaction.objectStore('pendingSync');
      const request = store.getAll();

      request.onsuccess = () => resolve(request.result || []);
      request.onerror = () => reject(new Error('Failed to get pending sync'));
    });
  }

  /**
   * Clear pending sync operations
   *
   * @param ids - Array of operation IDs to clear
   * @returns Promise resolving when cleared
   */
  async clearPendingSync(ids: string[]): Promise<void> {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(['pendingSync'], 'readwrite');
      const store = transaction.objectStore('pendingSync');

      ids.forEach((id) => store.delete(id));

      transaction.oncomplete = () => resolve();
      transaction.onerror = () =>
        reject(new Error('Failed to clear pending sync'));
    });
  }

  /**
   * Clear all offline data
   *
   * @returns Promise resolving when cleared
   */
  async clearAll(): Promise<void> {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(
        Object.keys(STORES),
        'readwrite'
      );

      Object.keys(STORES).forEach((storeName) => {
        transaction.objectStore(storeName).clear();
      });

      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(new Error('Failed to clear data'));
    });
  }

  /**
   * Get database storage estimate
   *
   * @returns Promise resolving to storage info
   */
  async getStorageEstimate(): Promise<{ usage: number; quota: number }> {
    if ('storage' in navigator && 'estimate' in navigator.storage) {
      const estimate = await navigator.storage.estimate();
      return {
        usage: estimate.usage || 0,
        quota: estimate.quota || 0,
      };
    }

    return { usage: 0, quota: 0 };
  }
}

// Create singleton instance
export const offlineStorage = new OfflineStorage();
