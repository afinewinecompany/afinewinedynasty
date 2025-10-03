/**
 * Custom hook for managing subscription state and operations.
 *
 * @module hooks/useSubscription
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import {
  getSubscriptionStatus,
  createCheckoutSession,
  cancelSubscription,
  reactivateSubscription,
  updatePaymentMethod,
} from '@/lib/api/subscriptions';
import type { SubscriptionStatus } from '@/types/subscription';

/**
 * Hook for fetching and managing subscription status
 * @returns Subscription status and loading state
 */
export function useSubscription() {
  const queryClient = useQueryClient();

  const {
    data: subscription,
    isLoading,
    error,
    refetch,
  } = useQuery<SubscriptionStatus>({
    queryKey: ['subscription', 'status'],
    queryFn: getSubscriptionStatus,
    staleTime: 5 * 60 * 1000, // 5 minutes
    cacheTime: 10 * 60 * 1000, // 10 minutes
  });

  // Check if user has premium access
  const isPremium = subscription?.tier === 'premium';
  const isActive =
    subscription?.status === 'active' || subscription?.status === 'trialing';

  // Check specific feature access
  const hasFeature = (feature: keyof SubscriptionStatus['features']) => {
    return subscription?.features?.[feature] || false;
  };

  // Invalidate subscription cache
  const invalidateSubscription = async () => {
    await queryClient.invalidateQueries(['subscription']);
  };

  return {
    subscription,
    isLoading,
    error,
    refetch,
    isPremium,
    isActive,
    hasFeature,
    invalidateSubscription,
    features: subscription?.features || {
      prospects_limit: 100,
      export_enabled: false,
      advanced_filters_enabled: false,
      comparison_enabled: false,
    },
  };
}

/**
 * Hook for initiating Stripe checkout
 * @returns Checkout mutation and loading state
 */
export function useCheckout() {
  const router = useRouter();
  const [isRedirecting, setIsRedirecting] = useState(false);

  const checkoutMutation = useMutation({
    mutationFn: (planId: string = 'premium') => createCheckoutSession(planId),
    onSuccess: (data) => {
      setIsRedirecting(true);
      // Redirect to Stripe checkout
      window.location.href = data.checkout_url;
    },
    onError: (error: any) => {
      setIsRedirecting(false);
      console.error('Checkout error:', error);
    },
  });

  return {
    initiateCheckout: checkoutMutation.mutate,
    isLoading: checkoutMutation.isLoading || isRedirecting,
    error: checkoutMutation.error,
  };
}

/**
 * Hook for managing subscription (cancel, reactivate)
 * @returns Subscription management functions
 */
export function useSubscriptionManagement() {
  const queryClient = useQueryClient();

  const cancelMutation = useMutation({
    mutationFn: (immediate: boolean = false) => cancelSubscription(immediate),
    onSuccess: () => {
      // Invalidate subscription cache to refresh status
      queryClient.invalidateQueries(['subscription']);
    },
  });

  const reactivateMutation = useMutation({
    mutationFn: reactivateSubscription,
    onSuccess: () => {
      // Invalidate subscription cache to refresh status
      queryClient.invalidateQueries(['subscription']);
    },
  });

  const updatePaymentMutation = useMutation({
    mutationFn: updatePaymentMethod,
    onSuccess: () => {
      // Invalidate subscription cache
      queryClient.invalidateQueries(['subscription']);
    },
  });

  return {
    // Cancel subscription
    cancelSubscription: cancelMutation.mutate,
    isCanceling: cancelMutation.isLoading,
    cancelError: cancelMutation.error,

    // Reactivate subscription
    reactivateSubscription: reactivateMutation.mutate,
    isReactivating: reactivateMutation.isLoading,
    reactivateError: reactivateMutation.error,

    // Update payment method
    updatePaymentMethod: updatePaymentMutation.mutate,
    isUpdatingPayment: updatePaymentMutation.isLoading,
    paymentError: updatePaymentMutation.error,
  };
}

/**
 * Hook for checking feature access
 * @param feature - Feature to check
 * @returns Boolean indicating if user has access
 */
export function useFeatureAccess(
  feature: keyof SubscriptionStatus['features']
) {
  const { subscription, isLoading } = useSubscription();

  if (isLoading) return { hasAccess: false, isLoading: true };

  const hasAccess = subscription?.features?.[feature] || false;

  return {
    hasAccess,
    isLoading: false,
    requiresUpgrade: !hasAccess && subscription?.tier === 'free',
  };
}
