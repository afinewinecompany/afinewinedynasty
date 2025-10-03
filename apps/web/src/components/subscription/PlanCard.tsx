/**
 * PlanCard component for displaying subscription plan details.
 *
 * @module components/subscription/PlanCard
 */

import React from 'react';
import { Check, X } from 'lucide-react';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import type { PlanDetails } from '@/types/subscription';

interface PlanCardProps {
  plan: PlanDetails;
  currentPlan?: boolean;
  onSelect?: () => void;
  isLoading?: boolean;
}

/**
 * Component for displaying a subscription plan card
 *
 * @param {PlanCardProps} props - Component props
 * @returns {JSX.Element} Rendered plan card
 */
export const PlanCard: React.FC<PlanCardProps> = ({
  plan,
  currentPlan = false,
  onSelect,
  isLoading = false,
}) => {
  return (
    <Card
      className={`relative ${plan.highlighted ? 'border-primary shadow-lg' : ''}`}
    >
      {plan.highlighted && (
        <Badge className="absolute -top-3 left-1/2 transform -translate-x-1/2">
          Most Popular
        </Badge>
      )}

      {currentPlan && (
        <Badge variant="secondary" className="absolute -top-3 right-4">
          Current Plan
        </Badge>
      )}

      <CardHeader>
        <CardTitle className="text-2xl">{plan.name}</CardTitle>
        <CardDescription>
          <span className="text-3xl font-bold">${plan.price}</span>
          {plan.price > 0 && (
            <span className="text-muted-foreground">/{plan.interval}</span>
          )}
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        <div className="space-y-2">
          <h4 className="font-semibold text-sm text-muted-foreground">
            Features
          </h4>
          <ul className="space-y-2">
            {plan.features.map((feature, index) => (
              <li key={index} className="flex items-start gap-2">
                <Check className="h-4 w-4 text-green-600 mt-0.5 flex-shrink-0" />
                <span className="text-sm">{feature}</span>
              </li>
            ))}
          </ul>
        </div>

        {plan.limitations && plan.limitations.length > 0 && (
          <div className="space-y-2 pt-2 border-t">
            <h4 className="font-semibold text-sm text-muted-foreground">
              Limitations
            </h4>
            <ul className="space-y-2">
              {plan.limitations.map((limitation, index) => (
                <li key={index} className="flex items-start gap-2">
                  <X className="h-4 w-4 text-red-600 mt-0.5 flex-shrink-0" />
                  <span className="text-sm text-muted-foreground">
                    {limitation}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>

      <CardFooter>
        {!currentPlan && onSelect && (
          <Button
            onClick={onSelect}
            disabled={isLoading}
            className="w-full"
            variant={plan.highlighted ? 'default' : 'outline'}
          >
            {isLoading
              ? 'Processing...'
              : plan.price === 0
                ? 'Get Started'
                : 'Subscribe Now'}
          </Button>
        )}
        {currentPlan && (
          <Button disabled className="w-full" variant="secondary">
            Your Current Plan
          </Button>
        )}
      </CardFooter>
    </Card>
  );
};
