/**
 * Subscription plans page for displaying available subscription options.
 *
 * @module app/subscription/page
 */

'use client';

import React from 'react';
import { useRouter } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { PlanCard } from '@/components/subscription/PlanCard';
import { useSubscription, useCheckout } from '@/hooks/useSubscription';
import { SUBSCRIPTION_PLANS } from '@/types/subscription';

/**
 * Subscription plans page component
 *
 * @returns {JSX.Element} Rendered subscription plans page
 */
export default function SubscriptionPlansPage() {
  const router = useRouter();
  const { subscription, isLoading: subscriptionLoading } = useSubscription();
  const { initiateCheckout, isLoading: checkoutLoading } = useCheckout();

  const handleSelectPlan = (planId: string) => {
    if (planId === 'free') {
      // Free plan - just redirect to home
      router.push('/');
    } else {
      // Premium plan - initiate checkout
      initiateCheckout(planId);
    }
  };

  return (
    <div className="container mx-auto py-8 px-4 max-w-6xl">
      <div className="mb-8">
        <Button
          variant="ghost"
          onClick={() => router.back()}
          className="mb-4"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back
        </Button>

        <div className="text-center space-y-4">
          <h1 className="text-4xl font-bold">Choose Your Plan</h1>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
            Get access to comprehensive prospect analysis, ML-powered predictions,
            and advanced tools to dominate your dynasty league.
          </p>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto">
        {SUBSCRIPTION_PLANS.map((plan) => (
          <PlanCard
            key={plan.id}
            plan={plan}
            currentPlan={subscription?.tier === plan.id}
            onSelect={() => handleSelectPlan(plan.id)}
            isLoading={checkoutLoading || subscriptionLoading}
          />
        ))}
      </div>

      <div className="mt-12 text-center space-y-4">
        <div className="flex items-center justify-center gap-8 text-sm text-muted-foreground">
          <div className="flex items-center gap-2">
            <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            <span>Cancel anytime</span>
          </div>
          <div className="flex items-center gap-2">
            <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M2.166 4.999A11.954 11.954 0 0010 1.944 11.954 11.954 0 0017.834 5c.11.65.166 1.32.166 2.001 0 5.225-3.34 9.67-8 11.317C5.34 16.67 2 12.225 2 7c0-.682.057-1.35.166-2.001zm11.541 3.708a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            <span>Secure payment via Stripe</span>
          </div>
          <div className="flex items-center gap-2">
            <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
              <path d="M2 3a1 1 0 011-1h2.153a1 1 0 01.986.836l.74 4.435a1 1 0 00.986.836h8.368a1 1 0 00.962-.726l1.371-4.799a1 1 0 00-.962-1.274H6.683a1 1 0 010-2h9.921a3 3 0 012.889 3.822l-1.371 4.799A3 3 0 0115.233 11H6.865a3 3 0 01-2.959-2.507l-.74-4.435L3.046 4H3a1 1 0 01-1-1z" />
              <path d="M5 16a2 2 0 100 4 2 2 0 000-4zM15 16a2 2 0 100 4 2 2 0 000-4z" />
            </svg>
            <span>No hidden fees</span>
          </div>
        </div>

        <p className="text-xs text-muted-foreground max-w-2xl mx-auto">
          By subscribing, you agree to our Terms of Service and Privacy Policy.
          Subscriptions auto-renew monthly. You can cancel or change your plan at any time.
        </p>
      </div>
    </div>
  );
}