/**
 * Service Worker for A Fine Wine Dynasty
 * Handles offline functionality, caching, and background sync
 *
 * @version 1.0.0
 */

// Cache configuration
const CACHE_VERSION = 'afwd-v1';
const CACHE_NAMES = {
  shell: `${CACHE_VERSION}-shell`,      // App shell, CSS, JS
  data: `${CACHE_VERSION}-data`,        // API responses
  images: `${CACHE_VERSION}-images`,    // Prospect images, logos
};

// URLs to cache on install (App Shell)
const STATIC_CACHE_URLS = [
  '/',
  '/offline',
  '/_next/static/css/app.css',
  '/fonts/inter.woff2',
  '/manifest.json',
  '/favicon.ico'
];

// Cache strategies for different resource types
const CACHE_STRATEGIES = {
  // App Shell: Cache-first with network fallback
  static: ['/', '/_next/static/', '/fonts/'],

  // API Data: Network-first with cache fallback
  api: ['/api/rankings', '/api/prospects/', '/api/search', '/api/discovery'],

  // Images: Cache-first with 7-day expiry
  images: ['/images/', 'cdn.mlb.com']
};

// Cache expiration times (in milliseconds)
const CACHE_EXPIRY = {
  data: 30 * 60 * 1000,        // 30 minutes
  images: 7 * 24 * 60 * 60 * 1000  // 7 days
};

/**
 * Install event - cache app shell
 */
self.addEventListener('install', (event) => {
  console.log('[Service Worker] Installing...');

  event.waitUntil(
    caches.open(CACHE_NAMES.shell)
      .then((cache) => {
        console.log('[Service Worker] Caching app shell');
        // Cache static URLs, but don't fail install if some URLs fail
        return Promise.allSettled(
          STATIC_CACHE_URLS.map(url =>
            cache.add(url).catch(err =>
              console.warn(`Failed to cache ${url}:`, err)
            )
          )
        );
      })
      .then(() => self.skipWaiting())
  );
});

/**
 * Activate event - clean old caches
 */
self.addEventListener('activate', (event) => {
  console.log('[Service Worker] Activating...');

  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((cacheName) => !Object.values(CACHE_NAMES).includes(cacheName))
          .map((cacheName) => {
            console.log('[Service Worker] Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          })
      );
    }).then(() => self.clients.claim())
  );
});

/**
 * Fetch event - implement caching strategies
 */
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests
  if (request.method !== 'GET') {
    return;
  }

  // Determine caching strategy
  const strategy = getCacheStrategy(url.pathname);

  switch (strategy) {
    case 'cache-first':
      event.respondWith(cacheFirst(request));
      break;
    case 'network-first':
      event.respondWith(networkFirst(request));
      break;
    case 'stale-while-revalidate':
      event.respondWith(staleWhileRevalidate(request));
      break;
    default:
      event.respondWith(fetch(request));
  }
});

/**
 * Background sync event
 */
self.addEventListener('sync', (event) => {
  console.log('[Service Worker] Background sync:', event.tag);

  if (event.tag === 'sync-data') {
    event.waitUntil(syncData());
  } else if (event.tag === 'sync-watchlist') {
    event.waitUntil(syncWatchlist());
  } else if (event.tag === 'sync-comparisons') {
    event.waitUntil(syncComparisons());
  }
});

/**
 * Message event - communicate with client
 */
self.addEventListener('message', (event) => {
  if (event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  } else if (event.data.type === 'CLEAR_CACHE') {
    clearAllCaches();
  } else if (event.data.type === 'CACHE_URLS') {
    cacheUrls(event.data.urls);
  }
});

/**
 * Determine cache strategy based on URL
 */
function getCacheStrategy(pathname) {
  // Static resources - cache first
  if (CACHE_STRATEGIES.static.some(pattern => pathname.includes(pattern))) {
    return 'cache-first';
  }

  // API data - network first
  if (CACHE_STRATEGIES.api.some(pattern => pathname.includes(pattern))) {
    return 'network-first';
  }

  // Images - stale while revalidate
  if (CACHE_STRATEGIES.images.some(pattern => pathname.includes(pattern))) {
    return 'stale-while-revalidate';
  }

  // Default - network only
  return 'network-only';
}

/**
 * Cache-first strategy
 */
async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) {
    return cached;
  }

  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_NAMES.shell);
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    // Return offline page if available
    return caches.match('/offline') || new Response('Offline', { status: 503 });
  }
}

/**
 * Network-first strategy
 */
async function networkFirst(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_NAMES.data);
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    const cached = await caches.match(request);
    if (cached) {
      // Check if cache is expired
      const cacheTime = cached.headers.get('sw-cache-time');
      if (cacheTime) {
        const age = Date.now() - parseInt(cacheTime);
        if (age < CACHE_EXPIRY.data) {
          return cached;
        }
      }
      return cached; // Return stale cache if no connection
    }
    return new Response('Network error', { status: 503 });
  }
}

/**
 * Stale-while-revalidate strategy
 */
async function staleWhileRevalidate(request) {
  const cached = await caches.match(request);

  const fetchPromise = fetch(request).then(response => {
    if (response.ok) {
      const cache = caches.open(CACHE_NAMES.images);
      cache.then(c => {
        // Add cache timestamp header
        const headers = new Headers(response.headers);
        headers.set('sw-cache-time', Date.now().toString());
        const responseWithTime = new Response(response.body, {
          status: response.status,
          statusText: response.statusText,
          headers: headers
        });
        c.put(request, responseWithTime);
      });
    }
    return response;
  }).catch(() => cached || new Response('Network error', { status: 503 }));

  return cached || fetchPromise;
}

/**
 * Sync data with server
 */
async function syncData() {
  try {
    // Notify client sync started
    const clients = await self.clients.matchAll();
    clients.forEach(client => {
      client.postMessage({ type: 'SYNC_START' });
    });

    // Perform sync operations
    await Promise.all([
      fetch('/api/rankings?sync=true'),
      fetch('/api/prospects/recent?sync=true')
    ]);

    // Notify client sync completed
    clients.forEach(client => {
      client.postMessage({ type: 'SYNC_COMPLETE' });
    });

    return true;
  } catch (error) {
    console.error('[Service Worker] Sync failed:', error);
    return false;
  }
}

/**
 * Sync watchlist data
 */
async function syncWatchlist() {
  try {
    // Get pending watchlist changes from IndexedDB
    const pendingChanges = await getPendingWatchlistChanges();

    if (pendingChanges.length > 0) {
      const response = await fetch('/api/watchlist/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ changes: pendingChanges })
      });

      if (response.ok) {
        await clearPendingWatchlistChanges();
      }
    }

    return true;
  } catch (error) {
    console.error('[Service Worker] Watchlist sync failed:', error);
    return false;
  }
}

/**
 * Sync comparison data
 */
async function syncComparisons() {
  try {
    // Get pending comparison data from IndexedDB
    const pendingComparisons = await getPendingComparisons();

    if (pendingComparisons.length > 0) {
      const response = await fetch('/api/comparisons/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ comparisons: pendingComparisons })
      });

      if (response.ok) {
        await clearPendingComparisons();
      }
    }

    return true;
  } catch (error) {
    console.error('[Service Worker] Comparison sync failed:', error);
    return false;
  }
}

/**
 * Clear all caches
 */
async function clearAllCaches() {
  const cacheNames = await caches.keys();
  await Promise.all(
    cacheNames.map(cacheName => caches.delete(cacheName))
  );
}

/**
 * Cache specific URLs
 */
async function cacheUrls(urls) {
  const cache = await caches.open(CACHE_NAMES.data);
  await Promise.all(
    urls.map(url => fetch(url).then(response => cache.put(url, response)))
  );
}

/**
 * Helper functions for IndexedDB operations
 * These integrate with the OfflineStorage class for pending sync data
 */

/**
 * Get pending watchlist changes from IndexedDB
 * @returns {Promise<Array>} Array of pending watchlist operations
 */
async function getPendingWatchlistChanges() {
  try {
    const db = await openDatabase();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(['pendingSync'], 'readonly');
      const store = transaction.objectStore('pendingSync');
      const index = store.index('by_type');
      const request = index.getAll(IDBKeyRange.bound('watchlist_', 'watchlist_\uffff'));

      request.onsuccess = () => resolve(request.result || []);
      request.onerror = () => reject(new Error('Failed to get pending changes'));
    });
  } catch (error) {
    console.error('[Service Worker] Failed to get pending watchlist changes:', error);
    return [];
  }
}

/**
 * Clear processed watchlist changes
 * @returns {Promise<boolean>} Success status
 */
async function clearPendingWatchlistChanges() {
  try {
    const changes = await getPendingWatchlistChanges();
    if (changes.length === 0) return true;

    const db = await openDatabase();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(['pendingSync'], 'readwrite');
      const store = transaction.objectStore('pendingSync');

      changes.forEach(change => store.delete(change.id));

      transaction.oncomplete = () => resolve(true);
      transaction.onerror = () => reject(new Error('Failed to clear changes'));
    });
  } catch (error) {
    console.error('[Service Worker] Failed to clear watchlist changes:', error);
    return false;
  }
}

/**
 * Get pending comparison data from IndexedDB
 * @returns {Promise<Array>} Array of pending comparison operations
 */
async function getPendingComparisons() {
  try {
    const db = await openDatabase();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(['pendingSync'], 'readonly');
      const store = transaction.objectStore('pendingSync');
      const index = store.index('by_type');
      const request = index.getAll(IDBKeyRange.bound('comparison_', 'comparison_\uffff'));

      request.onsuccess = () => resolve(request.result || []);
      request.onerror = () => reject(new Error('Failed to get pending comparisons'));
    });
  } catch (error) {
    console.error('[Service Worker] Failed to get pending comparisons:', error);
    return [];
  }
}

/**
 * Clear processed comparison data
 * @returns {Promise<boolean>} Success status
 */
async function clearPendingComparisons() {
  try {
    const comparisons = await getPendingComparisons();
    if (comparisons.length === 0) return true;

    const db = await openDatabase();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(['pendingSync'], 'readwrite');
      const store = transaction.objectStore('pendingSync');

      comparisons.forEach(comp => store.delete(comp.id));

      transaction.oncomplete = () => resolve(true);
      transaction.onerror = () => reject(new Error('Failed to clear comparisons'));
    });
  } catch (error) {
    console.error('[Service Worker] Failed to clear comparisons:', error);
    return false;
  }
}

/**
 * Open IndexedDB database
 * @returns {Promise<IDBDatabase>} Database instance
 */
function openDatabase() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('AFWDOfflineDB', 1);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(new Error('Failed to open database'));
  });
}