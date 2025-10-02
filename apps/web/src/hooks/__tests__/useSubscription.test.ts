/**
 * Test suite for subscription hooks.
 *
 * @module hooks/__tests__/useSubscription.test
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import {
  useSubscription,
  useCheckout,
  useSubscriptionManagement,
  useFeatureAccess
} from '../useSubscription';
import * as api from '@/lib/api/subscriptions';

// Mock the API module
jest.mock('@/lib/api/subscriptions');
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn(),
    back: jest.fn()
  })
}));
jest.mock('@/hooks/use-toast', () => ({
  useToast: () => ({
    toast: jest.fn()
  })
}));

describe('Subscription Hooks', () => {
  let queryClient: QueryClient;
  let wrapper: React.FC<{ children: React.ReactNode }>;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false }
      }
    });

    wrapper = ({ children }) => (
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    );

    jest.clearAllMocks();
  });

  describe('useSubscription', () => {
    it('should fetch subscription status', async () => {
      const mockSubscription = {
        status: 'active',
        tier: 'premium',
        plan_id: 'premium',
        current_period_start: '2025-01-01',
        current_period_end: '2025-02-01',
        cancel_at_period_end: false,
        features: {
          prospects_limit: 500,
          export_enabled: true,
          advanced_filters_enabled: true,
          comparison_enabled: true
        }
      };

      (api.getSubscriptionStatus as jest.Mock).mockResolvedValue(mockSubscription);

      const { result } = renderHook(() => useSubscription(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.subscription).toEqual(mockSubscription);
      expect(result.current.isPremium).toBe(true);
      expect(result.current.isActive).toBe(true);
      expect(result.current.features.prospects_limit).toBe(500);
    });

    it('should handle free tier correctly', async () => {
      const mockSubscription = {
        status: 'no_subscription',
        tier: 'free',
        features: {
          prospects_limit: 100,
          export_enabled: false,
          advanced_filters_enabled: false,
          comparison_enabled: false
        }
      };

      (api.getSubscriptionStatus as jest.Mock).mockResolvedValue(mockSubscription);

      const { result } = renderHook(() => useSubscription(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.isPremium).toBe(false);
      expect(result.current.isActive).toBe(false);
      expect(result.current.features.prospects_limit).toBe(100);
    });

    it('should check feature access correctly', async () => {
      const mockSubscription = {
        status: 'active',
        tier: 'premium',
        features: {
          prospects_limit: 500,
          export_enabled: true,
          advanced_filters_enabled: false,
          comparison_enabled: true
        }
      };

      (api.getSubscriptionStatus as jest.Mock).mockResolvedValue(mockSubscription);

      const { result } = renderHook(() => useSubscription(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.hasFeature('export_enabled')).toBe(true);
      expect(result.current.hasFeature('advanced_filters_enabled')).toBe(false);
    });
  });

  describe('useCheckout', () => {
    it('should initiate checkout and redirect', async () => {
      const mockCheckoutSession = {
        checkout_url: 'https://checkout.stripe.com/test',
        session_id: 'cs_test123',
        customer_id: 'cus_test123'
      };

      (api.createCheckoutSession as jest.Mock).mockResolvedValue(mockCheckoutSession);

      // Mock window.location
      delete (window as any).location;
      window.location = { href: '' } as Location;

      const { result } = renderHook(() => useCheckout(), { wrapper });

      await act(async () => {
        result.current.initiateCheckout('premium');
      });

      await waitFor(() => {
        expect(window.location.href).toBe(mockCheckoutSession.checkout_url);
      });

      expect(api.createCheckoutSession).toHaveBeenCalledWith('premium');
    });

    it('should handle checkout errors', async () => {
      const error = new Error('Checkout failed');
      (api.createCheckoutSession as jest.Mock).mockRejectedValue(error);

      const { result } = renderHook(() => useCheckout(), { wrapper });

      await act(async () => {
        result.current.initiateCheckout('premium');
      });

      await waitFor(() => {
        expect(result.current.error).toBeTruthy();
      });
    });
  });

  describe('useSubscriptionManagement', () => {
    it('should cancel subscription successfully', async () => {
      const mockResponse = {
        status: 'active',
        cancel_at_period_end: true,
        current_period_end: '2025-02-01',
        message: 'Subscription will be canceled'
      };

      (api.cancelSubscription as jest.Mock).mockResolvedValue(mockResponse);

      const { result } = renderHook(() => useSubscriptionManagement(), { wrapper });

      await act(async () => {
        result.current.cancelSubscription(false);
      });

      await waitFor(() => {
        expect(result.current.isCanceling).toBe(false);
      });

      expect(api.cancelSubscription).toHaveBeenCalledWith(false);
    });

    it('should reactivate subscription successfully', async () => {
      const mockResponse = {
        status: 'active',
        cancel_at_period_end: false,
        current_period_end: '2025-02-01',
        message: 'Subscription reactivated'
      };

      (api.reactivateSubscription as jest.Mock).mockResolvedValue(mockResponse);

      const { result } = renderHook(() => useSubscriptionManagement(), { wrapper });

      await act(async () => {
        result.current.reactivateSubscription();
      });

      await waitFor(() => {
        expect(result.current.isReactivating).toBe(false);
      });

      expect(api.reactivateSubscription).toHaveBeenCalled();
    });

    it('should update payment method successfully', async () => {
      const mockResponse = {
        card_brand: 'visa',
        last4: '4242',
        exp_month: 12,
        exp_year: 2025,
        is_default: true,
        message: 'Payment method updated'
      };

      (api.updatePaymentMethod as jest.Mock).mockResolvedValue(mockResponse);

      const { result } = renderHook(() => useSubscriptionManagement(), { wrapper });

      await act(async () => {
        result.current.updatePaymentMethod('pm_test123');
      });

      await waitFor(() => {
        expect(result.current.isUpdatingPayment).toBe(false);
      });

      expect(api.updatePaymentMethod).toHaveBeenCalledWith('pm_test123');
    });
  });

  describe('useFeatureAccess', () => {
    it('should check feature access correctly', async () => {
      const mockSubscription = {
        status: 'active',
        tier: 'premium',
        features: {
          prospects_limit: 500,
          export_enabled: true,
          advanced_filters_enabled: true,
          comparison_enabled: true
        }
      };

      (api.getSubscriptionStatus as jest.Mock).mockResolvedValue(mockSubscription);

      const { result } = renderHook(
        () => useFeatureAccess('export_enabled'),
        { wrapper }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.hasAccess).toBe(true);
      expect(result.current.requiresUpgrade).toBe(false);
    });

    it('should indicate upgrade required for free users', async () => {
      const mockSubscription = {
        status: 'no_subscription',
        tier: 'free',
        features: {
          prospects_limit: 100,
          export_enabled: false,
          advanced_filters_enabled: false,
          comparison_enabled: false
        }
      };

      (api.getSubscriptionStatus as jest.Mock).mockResolvedValue(mockSubscription);

      const { result } = renderHook(
        () => useFeatureAccess('export_enabled'),
        { wrapper }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.hasAccess).toBe(false);
      expect(result.current.requiresUpgrade).toBe(true);
    });
  });
});