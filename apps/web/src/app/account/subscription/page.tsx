/**
 * Account subscription management page.
 *
 * @module app/account/subscription/page
 */

'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowLeft, CreditCard, FileText } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { CurrentPlanCard } from '@/components/subscription/CurrentPlanCard';
import { PaymentMethodCard } from '@/components/subscription/PaymentMethodCard';
import { CancelSubscriptionModal } from '@/components/subscription/CancelSubscriptionModal';
import { CheckoutButton } from '@/components/subscription/CheckoutButton';
import { useSubscription } from '@/hooks/useSubscription';
import { format } from 'date-fns';

/**
 * Account subscription management page component
 *
 * @returns {JSX.Element} Rendered subscription management page
 */
export default function SubscriptionManagementPage() {
  const router = useRouter();
  const { subscription, isLoading, refetch } = useSubscription();
  const [showCancelModal, setShowCancelModal] = useState(false);

  const isPremium = subscription?.tier === 'premium';
  const currentPeriodEnd = subscription?.current_period_end
    ? format(new Date(subscription.current_period_end), 'MMMM d, yyyy')
    : undefined;

  if (isLoading) {
    return (
      <div className="container mx-auto py-8 px-4 max-w-4xl">
        <div className="text-center py-12">
          <p className="text-muted-foreground">Loading subscription details...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8 px-4 max-w-4xl">
      <div className="mb-8">
        <Button
          variant="ghost"
          onClick={() => router.back()}
          className="mb-4"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back
        </Button>

        <div className="space-y-2">
          <h1 className="text-3xl font-bold">Subscription & Billing</h1>
          <p className="text-muted-foreground">
            Manage your subscription plan and payment methods
          </p>
        </div>
      </div>

      <Tabs defaultValue="plan" className="space-y-6">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="plan">Plan</TabsTrigger>
          <TabsTrigger value="payment">Payment</TabsTrigger>
          <TabsTrigger value="invoices">Invoices</TabsTrigger>
        </TabsList>

        <TabsContent value="plan" className="space-y-6">
          <CurrentPlanCard />

          {isPremium ? (
            <div className="flex gap-3">
              <Button
                variant="outline"
                onClick={() => router.push('/subscription')}
              >
                View Plans
              </Button>
              {!subscription?.cancel_at_period_end && (
                <Button
                  variant="destructive"
                  onClick={() => setShowCancelModal(true)}
                >
                  Cancel Subscription
                </Button>
              )}
            </div>
          ) : (
            <div className="space-y-4">
              <div className="p-4 bg-muted rounded-lg">
                <h3 className="font-semibold mb-2">Upgrade to Premium</h3>
                <p className="text-sm text-muted-foreground mb-4">
                  Unlock full access to 500+ prospects, advanced analytics,
                  comparison tools, and data export capabilities.
                </p>
                <CheckoutButton>
                  Upgrade Now - $9.99/month
                </CheckoutButton>
              </div>
            </div>
          )}
        </TabsContent>

        <TabsContent value="payment" className="space-y-6">
          {isPremium ? (
            <PaymentMethodCard
              currentPaymentMethod={
                subscription && {
                  card_brand: 'visa', // This would come from the API
                  last4: '4242',
                  exp_month: 12,
                  exp_year: 2025
                }
              }
              onUpdate={() => refetch()}
            />
          ) : (
            <div className="text-center py-8">
              <CreditCard className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="font-semibold mb-2">No Payment Method Required</h3>
              <p className="text-sm text-muted-foreground mb-4">
                You're on the free plan. Upgrade to premium to add a payment method.
              </p>
              <CheckoutButton>
                Upgrade to Premium
              </CheckoutButton>
            </div>
          )}
        </TabsContent>

        <TabsContent value="invoices" className="space-y-6">
          {isPremium ? (
            <div className="space-y-4">
              <h3 className="font-semibold">Billing History</h3>
              <p className="text-sm text-muted-foreground">
                View and download your past invoices
              </p>
              {/* Invoice list would go here */}
              <div className="border rounded-lg p-8 text-center">
                <FileText className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <p className="text-sm text-muted-foreground">
                  Invoice history will appear here after your first payment.
                </p>
              </div>
            </div>
          ) : (
            <div className="text-center py-8">
              <FileText className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="font-semibold mb-2">No Invoices</h3>
              <p className="text-sm text-muted-foreground">
                You don't have any invoices on the free plan.
              </p>
            </div>
          )}
        </TabsContent>
      </Tabs>

      <CancelSubscriptionModal
        isOpen={showCancelModal}
        onClose={() => setShowCancelModal(false)}
        onSuccess={() => {
          refetch();
          setShowCancelModal(false);
        }}
        currentPeriodEnd={currentPeriodEnd}
      />
    </div>
  );
}