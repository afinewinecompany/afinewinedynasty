'use client';

import { useState, useCallback } from 'react';

interface ComparisonData {
  prospect_ids: number[];
  prospects: any[];
  comparison_metadata: {
    generated_at: string;
    prospects_count: number;
  };
  ml_comparison?: any;
  historical_analogs?: any;
  statistical_comparison?: any;
}

interface UseProspectComparisonReturn {
  comparisonData: ComparisonData | null;
  isLoading: boolean;
  error: string | null;
  fetchComparison: (prospectIds: number[]) => Promise<void>;
  clearComparison: () => void;
}

export function useProspectComparison(): UseProspectComparisonReturn {
  const [comparisonData, setComparisonData] = useState<ComparisonData | null>(
    null
  );
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchComparison = useCallback(async (prospectIds: number[]) => {
    if (prospectIds.length < 2 || prospectIds.length > 4) {
      setError('Must compare between 2-4 prospects');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams({
        prospect_ids: prospectIds.join(','),
        include_stats: 'true',
        include_predictions: 'true',
        include_analogs: 'true',
      });

      const response = await fetch(
        `/api/prospects/compare?${params.toString()}`,
        {
          headers: {
            Authorization: `Bearer ${localStorage.getItem('token')}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          errorData.detail || `HTTP ${response.status}: ${response.statusText}`
        );
      }

      const data = await response.json();
      setComparisonData(data);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to fetch comparison data';
      setError(errorMessage);
      console.error('Comparison fetch error:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const clearComparison = useCallback(() => {
    setComparisonData(null);
    setError(null);
  }, []);

  return {
    comparisonData,
    isLoading,
    error,
    fetchComparison,
    clearComparison,
  };
}

// Hook for fetching historical analogs
export function useComparisonAnalogs() {
  const [analogsData, setAnalogsData] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchAnalogs = useCallback(
    async (prospectIds: number[], limit: number = 3) => {
      setIsLoading(true);
      setError(null);

      try {
        const params = new URLSearchParams({
          prospect_ids: prospectIds.join(','),
          limit: limit.toString(),
        });

        const response = await fetch(
          `/api/prospects/compare/analogs?${params.toString()}`,
          {
            headers: {
              Authorization: `Bearer ${localStorage.getItem('token')}`,
            },
          }
        );

        if (!response.ok) {
          throw new Error(`Failed to fetch analogs: ${response.statusText}`);
        }

        const data = await response.json();
        setAnalogsData(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  return {
    analogsData,
    isLoading,
    error,
    fetchAnalogs,
  };
}

// Hook for exporting comparison data
export function useComparisonExport() {
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const exportComparison = useCallback(
    async (prospectIds: number[], format: 'pdf' | 'csv') => {
      setIsExporting(true);
      setError(null);

      try {
        const response = await fetch('/api/prospects/compare/export', {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${localStorage.getItem('token')}`,
            'Content-Type': 'application/x-www-form-urlencoded',
          },
          body: new URLSearchParams({
            prospect_ids: prospectIds.join(','),
            format,
          }),
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(
            errorData.detail || `Export failed: ${response.statusText}`
          );
        }

        const data = await response.json();

        // Return download information
        return {
          downloadUrl: data.download_url,
          filename: data.filename,
          format: data.format,
        };
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'Export failed';
        setError(errorMessage);
        throw err;
      } finally {
        setIsExporting(false);
      }
    },
    []
  );

  return {
    isExporting,
    error,
    exportComparison,
  };
}
