import { useState, useEffect, useCallback } from 'react';

interface QualityMetrics {
  quality_score: number;
  readability_score: number;
  coherence_score: number;
  sentence_count: number;
  word_count: number;
  grammar_issues: string[];
  content_issues: string[];
}

interface ProspectOutlook {
  narrative: string;
  quality_metrics: QualityMetrics;
  generated_at: string;
  template_version: string;
  model_version: string;
  risk_level: string;
  timeline: string;
  prospect_id: string;
  user_id?: string;
}

interface UseProspectOutlookResult {
  data: ProspectOutlook | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

export function useProspectOutlook(
  prospectId: string
): UseProspectOutlookResult {
  const [data, setData] = useState<ProspectOutlook | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchOutlook = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`/api/ml/outlook/${prospectId}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include', // Include cookies for authentication
      });

      if (!response.ok) {
        if (response.status === 404) {
          throw new Error('Prospect outlook not found');
        } else if (response.status === 429) {
          throw new Error('Rate limit exceeded. Please try again later.');
        } else if (response.status >= 500) {
          throw new Error('Server error. Please try again later.');
        } else {
          throw new Error(`Failed to fetch outlook: ${response.statusText}`);
        }
      }

      const outlook: ProspectOutlook = await response.json();
      setData(outlook);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'An unknown error occurred';
      setError(errorMessage);
      console.error('Error fetching prospect outlook:', err);
    } finally {
      setLoading(false);
    }
  }, [prospectId]);

  useEffect(() => {
    if (prospectId) {
      fetchOutlook();
    }
  }, [prospectId, fetchOutlook]);

  const refetch = useCallback(async () => {
    await fetchOutlook();
  }, [fetchOutlook]);

  return {
    data,
    loading,
    error,
    refetch,
  };
}

// Hook for batch outlook fetching (for rankings page)
interface UseBatchProspectOutlooksResult {
  data: Record<string, ProspectOutlook>;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

export function useBatchProspectOutlooks(
  prospectIds: string[]
): UseBatchProspectOutlooksResult {
  const [data, setData] = useState<Record<string, ProspectOutlook>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchBatchOutlooks = useCallback(async () => {
    if (!prospectIds.length) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const response = await fetch('/api/ml/batch-outlook', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          prospect_ids: prospectIds,
        }),
      });

      if (!response.ok) {
        if (response.status === 429) {
          throw new Error('Rate limit exceeded. Please try again later.');
        } else if (response.status >= 500) {
          throw new Error('Server error. Please try again later.');
        } else {
          throw new Error(`Failed to fetch outlooks: ${response.statusText}`);
        }
      }

      const outlooks: ProspectOutlook[] = await response.json();

      // Convert array to object keyed by prospect_id
      const outlookMap = outlooks.reduce(
        (acc, outlook) => {
          acc[outlook.prospect_id] = outlook;
          return acc;
        },
        {} as Record<string, ProspectOutlook>
      );

      setData(outlookMap);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'An unknown error occurred';
      setError(errorMessage);
      console.error('Error fetching batch outlooks:', err);
    } finally {
      setLoading(false);
    }
  }, [prospectIds]);

  useEffect(() => {
    fetchBatchOutlooks();
  }, [fetchBatchOutlooks]);

  const refetch = useCallback(async () => {
    await fetchBatchOutlooks();
  }, [fetchBatchOutlooks]);

  return {
    data,
    loading,
    error,
    refetch,
  };
}

// Hook for submitting outlook feedback
export function useOutlookFeedback() {
  const [submitting, setSubmitting] = useState(false);

  const submitFeedback = useCallback(
    async (
      prospectId: string,
      helpful: boolean,
      additionalFeedback?: string
    ) => {
      setSubmitting(true);
      try {
        const response = await fetch(`/api/ml/outlook/${prospectId}/feedback`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          credentials: 'include',
          body: JSON.stringify({
            helpful,
            additional_feedback: additionalFeedback,
            timestamp: new Date().toISOString(),
          }),
        });

        if (!response.ok) {
          throw new Error('Failed to submit feedback');
        }

        return true;
      } catch (error) {
        console.error('Error submitting feedback:', error);
        throw error;
      } finally {
        setSubmitting(false);
      }
    },
    []
  );

  return {
    submitFeedback,
    submitting,
  };
}
