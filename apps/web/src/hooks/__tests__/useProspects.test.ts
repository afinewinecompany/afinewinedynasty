import { renderHook, waitFor } from '@testing-library/react';
import { useProspects } from '../useProspects';
import { apiClient } from '@/lib/api/client';

// Mock the API client
jest.mock('@/lib/api/client', () => ({
  apiClient: {
    get: jest.fn(),
  },
}));

const mockApiClient = apiClient as jest.Mocked<typeof apiClient>;

describe('useProspects', () => {
  beforeEach(() => {
    mockApiClient.get.mockClear();
  });

  it('fetches prospects successfully', async () => {
    const mockResponse = {
      prospects: [
        {
          id: '1',
          mlb_id: 'mlb1',
          name: 'John Smith',
          position: 'SS',
          organization: 'New York Yankees',
          level: 'AAA',
          age: 22,
        },
      ],
      total: 1,
      page: 1,
      limit: 25,
      total_pages: 1,
    };

    mockApiClient.get.mockResolvedValueOnce(mockResponse);

    const { result } = renderHook(() => useProspects());

    expect(result.current.loading).toBe(true);
    expect(result.current.data).toBe(null);
    expect(result.current.error).toBe(null);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.data).toEqual(mockResponse);
    expect(result.current.error).toBe(null);
    expect(mockApiClient.get).toHaveBeenCalledWith(
      '/api/prospects?',
      30 // Cache for 30 minutes
    );
  });

  it('handles API errors correctly', async () => {
    const errorMessage = 'Network error';
    mockApiClient.get.mockRejectedValueOnce(new Error(errorMessage));

    const { result } = renderHook(() => useProspects());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.data).toBe(null);
    expect(result.current.error).toBe(errorMessage);
  });

  it('builds query parameters correctly', async () => {
    const params = {
      page: 2,
      limit: 50,
      position: 'SS',
      organization: 'Yankees',
      sort_by: 'age' as const,
      sort_order: 'desc' as const,
      search: 'Smith',
    };

    mockApiClient.get.mockResolvedValueOnce({
      prospects: [],
      total: 0,
      page: 2,
      limit: 50,
      total_pages: 0,
    });

    renderHook(() => useProspects(params));

    await waitFor(() => {
      expect(mockApiClient.get).toHaveBeenCalledWith(
        '/api/prospects?page=2&limit=50&position=SS&organization=Yankees&sort_by=age&sort_order=desc&search=Smith',
        30
      );
    });
  });

  it('refetch function works correctly', async () => {
    const mockResponse = {
      prospects: [],
      total: 0,
      page: 1,
      limit: 25,
      total_pages: 0,
    };

    mockApiClient.get.mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useProspects());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // Call refetch
    result.current.refetch();

    await waitFor(() => {
      expect(mockApiClient.get).toHaveBeenCalledTimes(2);
    });
  });

  it('updates when parameters change', async () => {
    mockApiClient.get.mockResolvedValue({
      prospects: [],
      total: 0,
      page: 1,
      limit: 25,
      total_pages: 0,
    });

    const { result, rerender } = renderHook(
      ({ params }) => useProspects(params),
      {
        initialProps: { params: { page: 1 } },
      }
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // Change parameters
    rerender({ params: { page: 2 } });

    await waitFor(() => {
      expect(mockApiClient.get).toHaveBeenCalledWith(
        '/api/prospects?page=2',
        30
      );
    });
  });

  it('handles empty parameters correctly', async () => {
    mockApiClient.get.mockResolvedValueOnce({
      prospects: [],
      total: 0,
      page: 1,
      limit: 25,
      total_pages: 0,
    });

    renderHook(() => useProspects({}));

    await waitFor(() => {
      expect(mockApiClient.get).toHaveBeenCalledWith('/api/prospects?', 30);
    });
  });

  it('handles non-Error exceptions', async () => {
    mockApiClient.get.mockRejectedValueOnce('String error');

    const { result } = renderHook(() => useProspects());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.error).toBe('Failed to fetch prospects');
  });
});
