import { APIClient, apiCache } from '../client';

// Mock fetch
global.fetch = jest.fn();

// Mock setTimeout/clearTimeout for timeout testing
jest.useFakeTimers();

describe('APIClient', () => {
  let client: APIClient;
  const mockFetch = global.fetch as jest.MockedFunction<typeof fetch>;

  beforeEach(() => {
    client = new APIClient({
      baseURL: 'https://api.example.com',
      timeout: 5000,
    });
    mockFetch.mockClear();
    apiCache.clear();
  });

  afterEach(() => {
    jest.clearAllTimers();
  });

  describe('HTTP methods', () => {
    it('makes GET requests correctly', async () => {
      const mockResponse = { data: 'test' };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve(mockResponse),
      } as Response);

      const result = await client.get('/test');

      expect(mockFetch).toHaveBeenCalledWith(
        'https://api.example.com/test',
        expect.objectContaining({
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          },
        })
      );
      expect(result).toEqual(mockResponse);
    });

    it('makes POST requests correctly', async () => {
      const mockResponse = { id: 1 };
      const requestBody = { name: 'Test' };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve(mockResponse),
      } as Response);

      const result = await client.post('/test', requestBody);

      expect(mockFetch).toHaveBeenCalledWith(
        'https://api.example.com/test',
        expect.objectContaining({
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(requestBody),
        })
      );
      expect(result).toEqual(mockResponse);
    });

    it('makes PUT requests correctly', async () => {
      const mockResponse = { id: 1, updated: true };
      const requestBody = { name: 'Updated' };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve(mockResponse),
      } as Response);

      const result = await client.put('/test/1', requestBody);

      expect(mockFetch).toHaveBeenCalledWith(
        'https://api.example.com/test/1',
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify(requestBody),
        })
      );
      expect(result).toEqual(mockResponse);
    });

    it('makes DELETE requests correctly', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ deleted: true }),
      } as Response);

      const result = await client.delete('/test/1');

      expect(mockFetch).toHaveBeenCalledWith(
        'https://api.example.com/test/1',
        expect.objectContaining({
          method: 'DELETE',
        })
      );
      expect(result).toEqual({ deleted: true });
    });
  });

  describe('Error handling', () => {
    it('throws error for non-ok responses', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
      } as Response);

      await expect(client.get('/test')).rejects.toThrow('HTTP error! status: 404');
    });

    it('throws error for network failures', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      await expect(client.get('/test')).rejects.toThrow('Network error');
    });

    it('handles timeout correctly', async () => {
      mockFetch.mockImplementationOnce(
        () => new Promise((resolve) => setTimeout(resolve, 10000))
      );

      const requestPromise = client.get('/test');

      // Fast-forward time to trigger timeout
      jest.advanceTimersByTime(35000);

      await expect(requestPromise).rejects.toThrow();
    }, 10000);
  });

  describe('Caching', () => {
    beforeEach(() => {
      apiCache.clear();
    });

    it('caches GET requests when cache time is specified', async () => {
      const mockResponse = { data: 'cached' };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve(mockResponse),
      } as Response);

      // First request
      const result1 = await client.get('/test', 30);
      expect(mockFetch).toHaveBeenCalledTimes(1);
      expect(result1).toEqual(mockResponse);

      // Second request should use cache
      const result2 = await client.get('/test', 30);
      expect(mockFetch).toHaveBeenCalledTimes(1); // Still only one fetch call
      expect(result2).toEqual(mockResponse);
    });

    it('does not cache POST requests', async () => {
      const mockResponse = { data: 'not cached' };
      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        json: () => Promise.resolve(mockResponse),
      } as Response);

      // First request
      await client.post('/test', { data: 'test' });
      expect(mockFetch).toHaveBeenCalledTimes(1);

      // Second request should not use cache
      await client.post('/test', { data: 'test' });
      expect(mockFetch).toHaveBeenCalledTimes(2);
    });

    it('respects cache TTL', async () => {
      const mockResponse = { data: 'expired' };
      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        json: () => Promise.resolve(mockResponse),
      } as Response);

      // First request
      await client.get('/test', 1); // 1 minute cache

      // Advance time by 2 minutes
      jest.advanceTimersByTime(2 * 60 * 1000);

      // Second request should fetch again
      await client.get('/test', 1);
      expect(mockFetch).toHaveBeenCalledTimes(2);
    });
  });

  describe('Request headers', () => {
    it('includes default headers', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({}),
      } as Response);

      await client.get('/test');

      expect(mockFetch).toHaveBeenCalledWith(
        'https://api.example.com/test',
        expect.objectContaining({
          headers: {
            'Content-Type': 'application/json',
          },
        })
      );
    });

    it('merges custom headers with defaults', async () => {
      const clientWithHeaders = new APIClient({
        baseURL: 'https://api.example.com',
        headers: {
          'Authorization': 'Bearer token',
          'X-Custom': 'value',
        },
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({}),
      } as Response);

      await clientWithHeaders.get('/test');

      expect(mockFetch).toHaveBeenCalledWith(
        'https://api.example.com/test',
        expect.objectContaining({
          headers: expect.objectContaining({
            'Authorization': 'Bearer token',
            'X-Custom': 'value',
          }),
        })
      );
    });
  });
});

describe('APICache', () => {
  beforeEach(() => {
    apiCache.clear();
  });

  it('stores and retrieves cached data', () => {
    const data = { test: 'value' };
    apiCache.set('key1', data, 30);

    const result = apiCache.get('key1');
    expect(result).toEqual(data);
  });

  it('returns null for non-existent keys', () => {
    const result = apiCache.get('nonexistent');
    expect(result).toBeNull();
  });

  it('expires cached data after TTL', () => {
    const data = { test: 'value' };
    apiCache.set('key1', data, 1); // 1 minute

    // Advance time by 2 minutes
    jest.advanceTimersByTime(2 * 60 * 1000);

    const result = apiCache.get('key1');
    expect(result).toBeNull();
  });

  it('deletes specific keys', () => {
    apiCache.set('key1', { data: 1 }, 30);
    apiCache.set('key2', { data: 2 }, 30);

    apiCache.delete('key1');

    expect(apiCache.get('key1')).toBeNull();
    expect(apiCache.get('key2')).toEqual({ data: 2 });
  });

  it('clears all cached data', () => {
    apiCache.set('key1', { data: 1 }, 30);
    apiCache.set('key2', { data: 2 }, 30);

    apiCache.clear();

    expect(apiCache.get('key1')).toBeNull();
    expect(apiCache.get('key2')).toBeNull();
  });
});