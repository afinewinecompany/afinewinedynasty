interface CacheEntry<T> {
  data: T;
  timestamp: number;
  ttl: number;
}

class APICache {
  private cache = new Map<string, CacheEntry<unknown>>();

  set<T>(key: string, data: T, ttlMinutes: number): void {
    const ttl = ttlMinutes * 60 * 1000; // Convert to milliseconds
    this.cache.set(key, {
      data,
      timestamp: Date.now(),
      ttl,
    });
  }

  get<T>(key: string): T | null {
    const entry = this.cache.get(key);
    if (!entry) return null;

    const now = Date.now();
    if (now - entry.timestamp > entry.ttl) {
      this.cache.delete(key);
      return null;
    }

    return entry.data as T;
  }

  clear(): void {
    this.cache.clear();
  }

  delete(key: string): void {
    this.cache.delete(key);
  }
}

export const apiCache = new APICache();

export interface APIClientConfig {
  baseURL: string;
  timeout?: number;
  headers?: Record<string, string>;
}

export class APIClient {
  private config: APIClientConfig;

  constructor(config: APIClientConfig) {
    this.config = {
      timeout: 30000, // 30 seconds default
      headers: {
        'Content-Type': 'application/json',
      },
      ...config,
    };
  }

  private getAuthHeaders(): HeadersInit {
    // Check if we're in browser environment
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('access_token');
      if (token) {
        return { Authorization: `Bearer ${token}` };
      }
    }
    return {};
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
    cacheMinutes?: number
  ): Promise<T> {
    const url = `${this.config.baseURL}${endpoint}`;
    const cacheKey = `${url}:${JSON.stringify(options)}`;

    // Check cache first if caching is enabled
    if (cacheMinutes && options.method !== 'POST') {
      const cachedData = apiCache.get<T>(cacheKey);
      if (cachedData) {
        return cachedData;
      }
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.config.timeout);

    try {
      const response = await fetch(url, {
        ...options,
        headers: {
          ...this.config.headers,
          ...this.getAuthHeaders(),
          ...options.headers,
        },
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        // Try to get error details from response body
        let errorDetail = `HTTP ${response.status}`;
        try {
          const errorBody = await response.json();
          console.error('[APIClient] Error response:', errorBody);
          console.error('[APIClient] Error response (stringified):', JSON.stringify(errorBody, null, 2));

          // Handle different error formats
          if (errorBody.detail) {
            if (Array.isArray(errorBody.detail)) {
              // ValidationError format: detail is array of error objects
              errorDetail = errorBody.detail.map((err: any) =>
                typeof err === 'string' ? err : err.msg || JSON.stringify(err)
              ).join(', ');
            } else if (typeof errorBody.detail === 'object') {
              errorDetail = JSON.stringify(errorBody.detail);
            } else {
              errorDetail = errorBody.detail;
            }
          } else if (errorBody.message) {
            errorDetail = errorBody.message;
          }
        } catch {
          // Response might not be JSON
          const errorText = await response.text();
          console.error('[APIClient] Error text:', errorText);
          if (errorText) errorDetail = errorText;
        }
        throw new Error(`API Error: ${errorDetail}`);
      }

      const data = await response.json();

      // Cache successful responses
      if (cacheMinutes && response.status === 200) {
        apiCache.set(cacheKey, data, cacheMinutes);
      }

      return data;
    } catch (error) {
      clearTimeout(timeoutId);
      throw error;
    }
  }

  async get<T>(endpoint: string, cacheMinutes?: number): Promise<T> {
    return this.request<T>(endpoint, { method: 'GET' }, cacheMinutes);
  }

  async post<T>(endpoint: string, body?: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  async put<T>(endpoint: string, body?: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  async delete<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'DELETE' });
  }
}

// Default API client instance
const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const apiVersion = process.env.NEXT_PUBLIC_API_VERSION || 'v1';
export const apiClient = new APIClient({
  baseURL: `${apiBaseUrl}/api/${apiVersion}`,
});

// Export as 'api' for compatibility
export const api = apiClient;
