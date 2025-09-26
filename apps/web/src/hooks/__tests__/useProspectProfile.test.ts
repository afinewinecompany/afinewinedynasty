import { renderHook, waitFor } from '@testing-library/react';
import { useProspectProfile } from '../useProspectProfile';
import { apiClient } from '@/lib/api/client';

// Mock the API client
jest.mock('@/lib/api/client', () => ({
  apiClient: {
    get: jest.fn(),
  },
}));

const mockApiClient = apiClient as jest.Mocked<typeof apiClient>;

describe('useProspectProfile', () => {
  beforeEach(() => {
    mockApiClient.get.mockClear();
  });

  it('fetches prospect profile successfully', async () => {
    const mockResponse = {
      id: '1',
      mlb_id: 'mlb1',
      name: 'John Smith',
      position: 'SS',
      organization: 'New York Yankees',
      level: 'AAA',
      age: 22,
      stats: [],
      ml_prediction: {
        prospect_id: '1',
        success_probability: 0.75,
        confidence_level: 'High' as const,
        generated_at: '2024-01-01T00:00:00Z',
      },
    };

    mockApiClient.get.mockResolvedValueOnce(mockResponse);

    const { result } = renderHook(() => useProspectProfile('1'));

    expect(result.current.loading).toBe(true);
    expect(result.current.data).toBe(null);
    expect(result.current.error).toBe(null);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.data).toEqual(mockResponse);
    expect(result.current.error).toBe(null);
    expect(mockApiClient.get).toHaveBeenCalledWith(
      '/api/prospects/1',
      60 // Cache for 1 hour
    );
  });

  it('handles API errors correctly', async () => {
    const errorMessage = 'Network error';
    mockApiClient.get.mockRejectedValueOnce(new Error(errorMessage));

    const { result } = renderHook(() => useProspectProfile('1'));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.data).toBe(null);
    expect(result.current.error).toBe(errorMessage);
  });

  it('does not fetch when id is empty', async () => {
    const { result } = renderHook(() => useProspectProfile(''));

    expect(result.current.loading).toBe(true);
    expect(result.current.data).toBe(null);
    expect(result.current.error).toBe(null);
    expect(mockApiClient.get).not.toHaveBeenCalled();
  });

  it('refetch function works correctly', async () => {
    const mockResponse = {
      id: '1',
      mlb_id: 'mlb1',
      name: 'John Smith',
      position: 'SS',
      organization: 'New York Yankees',
      level: 'AAA',
      age: 22,
    };

    mockApiClient.get.mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useProspectProfile('1'));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // Call refetch
    result.current.refetch();

    await waitFor(() => {
      expect(mockApiClient.get).toHaveBeenCalledTimes(2);
    });
  });

  it('updates when id changes', async () => {
    mockApiClient.get.mockResolvedValue({
      id: '1',
      mlb_id: 'mlb1',
      name: 'John Smith',
      position: 'SS',
      organization: 'New York Yankees',
      level: 'AAA',
      age: 22,
    });

    const { result, rerender } = renderHook(
      ({ id }) => useProspectProfile(id),
      {
        initialProps: { id: '1' },
      }
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // Change ID
    rerender({ id: '2' });

    await waitFor(() => {
      expect(mockApiClient.get).toHaveBeenCalledWith('/api/prospects/2', 60);
    });
  });

  it('handles non-Error exceptions', async () => {
    mockApiClient.get.mockRejectedValueOnce('String error');

    const { result } = renderHook(() => useProspectProfile('1'));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.error).toBe('Failed to fetch prospect profile');
  });
});