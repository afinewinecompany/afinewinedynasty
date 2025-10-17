/**
 * Subscription Tab Component
 *
 * Displays current subscription status, billing information, and plan management.
 * Allows upgrading, downgrading, and canceling subscriptions.
 *
 * @component SubscriptionTab
 * @since 1.0.0
 */

'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { CurrentPlanCard } from '@/components/subscription/CurrentPlanCard';
import { PaymentMethodCard } from '@/components/subscription/PaymentMethodCard';
import { CancelSubscriptionModal } from '@/components/subscription/CancelSubscriptionModal';
import { useSubscription, useCheckout } from '@/hooks/useSubscription';
import {
  CreditCard,
  Crown,
  TrendingUp,
  AlertCircle,
  ExternalLink,
  Loader2,
} from 'lucide-react';

/**
 * Subscription management tab
 *
 * @returns {JSX.Element} Rendered subscription management interface
 *
 * @example
 * ```tsx
 * <SubscriptionTab />
 * ```
 *
 * @since 1.0.0
 */
export function SubscriptionTab(): JSX.Element {
  const router = useRouter();
  const { subscription, isLoading } = useSubscription();
  const { initiateCheckout, isLoading: checkoutLoading } = useCheckout();
  const [showCancelModal, setShowCancelModal] = useState(false);

  const isPremium = subscription?.tier === 'premium';
  const isActive = subscription?.status === 'active';
  const willCancel = subscription?.cancel_at_period_end;

  /**
   * Handle upgrade to premium
   */
  const handleUpgrade = () => {
    initiateCheckout('premium');
  };

  /**
   * Navigate to subscription plans page
   */
  const handleViewPlans = () => {
    router.push('/subscription');
  };

  if (isLoading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
          <span className="ml-2 text-gray-600">Loading subscription...</span>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Current Plan Card */}
      <CurrentPlanCard />

      {/* Upgrade Prompt (Free Users) */}
      {!isPremium && (
        <Card className="border-2 border-yellow-200 bg-gradient-to-br from-yellow-50 to-orange-50">
          <CardHeader>
            <div className="flex items-center gap-2">
              <Crown className="h-5 w-5 text-yellow-500" />
              <CardTitle>Unlock Premium Features</CardTitle>
            </div>
            <CardDescription>
              Upgrade to Premium and get access to powerful dynasty league tools
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="flex items-start gap-2">
                <div className="h-5 w-5 rounded-full bg-green-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <svg
                    className="h-3 w-3 text-green-600"
                    fill="none"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path d="M5 13l4 4L19 7"></path>
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-medium">Full Top 500 Rankings</p>
                  <p className="text-xs text-muted-foreground">
                    Access complete prospect database
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-2">
                <div className="h-5 w-5 rounded-full bg-green-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <svg
                    className="h-3 w-3 text-green-600"
                    fill="none"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path d="M5 13l4 4L19 7"></path>
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-medium">Advanced Filtering</p>
                  <p className="text-xs text-muted-foreground">
                    Search by position, ETA, team & more
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-2">
                <div className="h-5 w-5 rounded-full bg-green-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <svg
                    className="h-3 w-3 text-green-600"
                    fill="none"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path d="M5 13l4 4L19 7"></path>
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-medium">Fantrax Integration</p>
                  <p className="text-xs text-muted-foreground">
                    Personalized recommendations for your team
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-2">
                <div className="h-5 w-5 rounded-full bg-green-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <svg
                    className="h-3 w-3 text-green-600"
                    fill="none"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path d="M5 13l4 4L19 7"></path>
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-medium">Prospect Comparisons</p>
                  <p className="text-xs text-muted-foreground">
                    Side-by-side analysis tools
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-2">
                <div className="h-5 w-5 rounded-full bg-green-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <svg
                    className="h-3 w-3 text-green-600"
                    fill="none"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path d="M5 13l4 4L19 7"></path>
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-medium">Data Export</p>
                  <p className="text-xs text-muted-foreground">
                    Export rankings to CSV/Excel
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-2">
                <div className="h-5 w-5 rounded-full bg-green-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <svg
                    className="h-3 w-3 text-green-600"
                    fill="none"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path d="M5 13l4 4L19 7"></path>
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-medium">Historical Data</p>
                  <p className="text-xs text-muted-foreground">
                    Access past seasons & trends
                  </p>
                </div>
              </div>
            </div>

            <div className="pt-4 border-t flex items-center justify-between">
              <div>
                <p className="text-2xl font-bold">$9.99<span className="text-base font-normal text-muted-foreground">/month</span></p>
                <p className="text-xs text-muted-foreground">Cancel anytime, no commitment</p>
              </div>
              <Button onClick={handleUpgrade} disabled={checkoutLoading} size="lg">
                {checkoutLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Processing...
                  </>
                ) : (
                  <>
                    <TrendingUp className="mr-2 h-4 w-4" />
                    Upgrade to Premium
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Payment Method (Premium Users) */}
      {isPremium && isActive && (
        <PaymentMethodCard />
      )}

      {/* Cancellation Warning */}
      {willCancel && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            Your subscription will be canceled at the end of the current billing period.
            You'll lose access to premium features after that date.
          </AlertDescription>
        </Alert>
      )}

      {/* Plan Management Actions */}
      <Card>
        <CardHeader>
          <CardTitle>Plan Management</CardTitle>
          <CardDescription>Manage your subscription and billing</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
            <div>
              <p className="font-medium text-gray-900">View All Plans</p>
              <p className="text-sm text-gray-600">Compare features and pricing</p>
            </div>
            <Button variant="outline" onClick={handleViewPlans}>
              <ExternalLink className="mr-2 h-4 w-4" />
              View Plans
            </Button>
          </div>

          {isPremium && isActive && !willCancel && (
            <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
              <div>
                <p className="font-medium text-gray-900">Cancel Subscription</p>
                <p className="text-sm text-gray-600">
                  End your subscription at the end of the billing period
                </p>
              </div>
              <Button variant="outline" onClick={() => setShowCancelModal(true)}>
                Cancel Plan
              </Button>
            </div>
          )}

          <div className="text-xs text-gray-500 text-center pt-4 border-t">
            <p>
              Questions about billing?{' '}
              <a href="mailto:support@afinewinedynasty.com" className="text-blue-600 hover:underline">
                Contact Support
              </a>
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Cancel Subscription Modal */}
      {showCancelModal && (
        <CancelSubscriptionModal
          isOpen={showCancelModal}
          onClose={() => setShowCancelModal(false)}
        />
      )}
    </div>
  );
}
