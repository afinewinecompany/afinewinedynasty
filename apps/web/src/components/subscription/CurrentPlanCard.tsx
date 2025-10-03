/**
 * CurrentPlanCard component for displaying current subscription details.
 *
 * @module components/subscription/CurrentPlanCard
 */

import React from 'react';
import { Calendar, CreditCard, AlertCircle } from 'lucide-react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  useSubscription,
  useSubscriptionManagement,
} from '@/hooks/useSubscription';
import { format } from 'date-fns';

/**
 * Component for displaying current subscription plan details
 *
 * @returns {JSX.Element} Rendered current plan card
 */
export const CurrentPlanCard: React.FC = () => {
  const { subscription, isLoading } = useSubscription();
  const { reactivateSubscription, isReactivating } =
    useSubscriptionManagement();

  if (isLoading) {
    return (
      <Card>
        <CardContent className="py-6">
          <div className="text-center">Loading subscription details...</div>
        </CardContent>
      </Card>
    );
  }

  if (!subscription || subscription.tier === 'free') {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Current Plan</CardTitle>
          <CardDescription>Free Plan</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground mb-4">
            You're currently on the free plan with limited features.
          </p>
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm">
              <span className="font-medium">Prospect Limit:</span>
              <span>{subscription?.features.prospects_limit || 100}</span>
            </div>
            <div className="flex items-center gap-2 text-sm">
              <span className="font-medium">Data Export:</span>
              <Badge variant="secondary">Not Available</Badge>
            </div>
            <div className="flex items-center gap-2 text-sm">
              <span className="font-medium">Advanced Features:</span>
              <Badge variant="secondary">Limited</Badge>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  const nextBillingDate = subscription.current_period_end
    ? format(new Date(subscription.current_period_end), 'MMMM d, yyyy')
    : 'N/A';

  const planStartDate = subscription.current_period_start
    ? format(new Date(subscription.current_period_start), 'MMMM d, yyyy')
    : 'N/A';

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Current Plan</CardTitle>
            <CardDescription>Premium Subscription</CardDescription>
          </div>
          <Badge
            variant={subscription.status === 'active' ? 'default' : 'secondary'}
          >
            {subscription.status}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {subscription.cancel_at_period_end && (
          <Alert>
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              Your subscription will be canceled at the end of the billing
              period on {nextBillingDate}.
              <Button
                variant="link"
                size="sm"
                onClick={() => reactivateSubscription()}
                disabled={isReactivating}
                className="ml-2"
              >
                Undo cancellation
              </Button>
            </AlertDescription>
          </Alert>
        )}

        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <CreditCard className="h-4 w-4 text-muted-foreground" />
            <div className="flex-1">
              <p className="text-sm font-medium">Billing Amount</p>
              <p className="text-sm text-muted-foreground">$9.99/month</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Calendar className="h-4 w-4 text-muted-foreground" />
            <div className="flex-1">
              <p className="text-sm font-medium">Current Period</p>
              <p className="text-sm text-muted-foreground">
                {planStartDate} - {nextBillingDate}
              </p>
            </div>
          </div>

          {!subscription.cancel_at_period_end && (
            <div className="flex items-center gap-2">
              <Calendar className="h-4 w-4 text-muted-foreground" />
              <div className="flex-1">
                <p className="text-sm font-medium">Next Billing Date</p>
                <p className="text-sm text-muted-foreground">
                  {nextBillingDate}
                </p>
              </div>
            </div>
          )}
        </div>

        <div className="pt-4 border-t">
          <h4 className="text-sm font-medium mb-2">Premium Features</h4>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div className="flex items-center gap-1">
              <Badge variant="outline" className="text-xs">
                500
              </Badge>
              <span className="text-muted-foreground">Prospects</span>
            </div>
            <div className="flex items-center gap-1">
              <Badge variant="outline" className="text-xs">
                ✓
              </Badge>
              <span className="text-muted-foreground">Data Export</span>
            </div>
            <div className="flex items-center gap-1">
              <Badge variant="outline" className="text-xs">
                ✓
              </Badge>
              <span className="text-muted-foreground">Comparisons</span>
            </div>
            <div className="flex items-center gap-1">
              <Badge variant="outline" className="text-xs">
                ✓
              </Badge>
              <span className="text-muted-foreground">Advanced Filters</span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};
