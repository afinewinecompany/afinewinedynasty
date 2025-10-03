/**
 * React hook for analytics event tracking.
 *
 * @hook useAnalytics
 * @since 1.0.0
 */

import { useCallback } from 'react';
import { apiClient } from '@/lib/api/client';

export function useAnalytics() {
  const trackEvent = useCallback(async (
    eventName: string,
    eventData?: Record<string, any>
  ) => {
    try {
      await apiClient.post('/analytics/track', {
        event_name: eventName,
        event_data: eventData
      });
    } catch (error) {
      console.error('Analytics tracking error:', error);
    }
  }, []);

  return { trackEvent };
}
