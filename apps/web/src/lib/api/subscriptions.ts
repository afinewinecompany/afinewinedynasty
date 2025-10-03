/**
 * Subscription API client for managing subscriptions and payments.
 *
 * @module lib/api/subscriptions
 */

import { apiClient } from './client';
import type {
  Subscription,
  SubscriptionStatus,
  CheckoutSession,
  PaymentMethod,
  Invoice,
} from '@/types/subscription';

/**
 * Create a Stripe checkout session for subscription
 * @param planId - Subscription plan ID
 * @returns Promise with checkout session details
 */
export async function createCheckoutSession(
  planId: string = 'premium'
): Promise<CheckoutSession> {
  const response = await apiClient.post('/subscriptions/checkout-session', {
    plan_id: planId,
  });
  return response.data;
}

/**
 * Get current user's subscription status
 * @returns Promise with subscription status
 */
export async function getSubscriptionStatus(): Promise<SubscriptionStatus> {
  const response = await apiClient.get('/subscriptions/status');
  return response.data;
}

/**
 * Cancel user's subscription
 * @param immediate - Cancel immediately vs at period end
 * @returns Promise with updated subscription details
 */
export async function cancelSubscription(immediate: boolean = false): Promise<{
  status: string;
  cancel_at_period_end: boolean;
  current_period_end: string;
  message: string;
}> {
  const response = await apiClient.post('/subscriptions/cancel', { immediate });
  return response.data;
}

/**
 * Reactivate a canceled subscription
 * @returns Promise with updated subscription details
 */
export async function reactivateSubscription(): Promise<{
  status: string;
  cancel_at_period_end: boolean;
  current_period_end: string;
  message: string;
}> {
  const response = await apiClient.post('/subscriptions/reactivate');
  return response.data;
}

/**
 * Update payment method
 * @param paymentMethodId - Stripe payment method ID
 * @returns Promise with updated payment method details
 */
export async function updatePaymentMethod(
  paymentMethodId: string
): Promise<PaymentMethod & { message: string }> {
  const response = await apiClient.put('/subscriptions/payment-method', {
    payment_method_id: paymentMethodId,
  });
  return response.data;
}

/**
 * Get user's invoices
 * @param limit - Number of invoices to fetch
 * @returns Promise with invoice list
 */
export async function getUserInvoices(limit: number = 10): Promise<Invoice[]> {
  // This would be implemented when the endpoint is added
  const response = await apiClient.get(
    `/subscriptions/invoices?limit=${limit}`
  );
  return response.data.invoices;
}

/**
 * Check if user has access to a specific feature
 * @param feature - Feature to check
 * @returns Promise with boolean indicating access
 */
export async function checkFeatureAccess(feature: string): Promise<boolean> {
  const status = await getSubscriptionStatus();
  const features = status.features as any;
  return features[feature] || false;
}
