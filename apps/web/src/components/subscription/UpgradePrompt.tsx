/**
 * UpgradePrompt component for prompting users to upgrade their subscription.
 *
 * @module components/subscription/UpgradePrompt
 */

import React from 'react';
import { Lock, Sparkles, TrendingUp, Download } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Card, CardContent } from '@/components/ui/card';
import { CheckoutButton } from './CheckoutButton';

interface UpgradePromptProps {
  feature?: 'prospects' | 'export' | 'comparison' | 'filters' | 'general';
  variant?: 'inline' | 'card' | 'alert';
  className?: string;
}

/**
 * Component for prompting users to upgrade to premium
 *
 * @param {UpgradePromptProps} props - Component props
 * @returns {JSX.Element} Rendered upgrade prompt
 */
export const UpgradePrompt: React.FC<UpgradePromptProps> = ({
  feature = 'general',
  variant = 'alert',
  className = '',
}) => {
  const featureMessages = {
    prospects: {
      icon: <TrendingUp className="h-5 w-5" />,
      title: 'Access All 500+ Prospects',
      description:
        'Upgrade to Premium to view the complete top 500 prospects ranking and unlock detailed analytics for every player.',
    },
    export: {
      icon: <Download className="h-5 w-5" />,
      title: 'Export Your Data',
      description:
        'Premium members can export prospect data in CSV or JSON format for custom analysis and integration.',
    },
    comparison: {
      icon: <Sparkles className="h-5 w-5" />,
      title: 'Compare Prospects Side-by-Side',
      description:
        'Unlock the comparison tool to analyze multiple prospects simultaneously with advanced metrics and visualizations.',
    },
    filters: {
      icon: <Lock className="h-5 w-5" />,
      title: 'Advanced Filtering & Search',
      description:
        'Get access to advanced filters, custom searches, and ML-powered prospect discovery tools.',
    },
    general: {
      icon: <Sparkles className="h-5 w-5" />,
      title: 'Upgrade to Premium',
      description:
        'Unlock all features including 500+ prospects, advanced analytics, comparison tools, and data export.',
    },
  };

  const message = featureMessages[feature];

  if (variant === 'inline') {
    return (
      <div
        className={`flex items-center gap-2 p-4 bg-muted/50 rounded-lg ${className}`}
      >
        <Lock className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm text-muted-foreground flex-1">
          {message.description}
        </span>
        <CheckoutButton size="sm" variant="outline">
          Upgrade
        </CheckoutButton>
      </div>
    );
  }

  if (variant === 'card') {
    return (
      <Card className={className}>
        <CardContent className="pt-6">
          <div className="text-center space-y-4">
            <div className="mx-auto w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center">
              {message.icon}
            </div>
            <div className="space-y-2">
              <h3 className="font-semibold text-lg">{message.title}</h3>
              <p className="text-sm text-muted-foreground max-w-sm mx-auto">
                {message.description}
              </p>
            </div>
            <div className="pt-2">
              <CheckoutButton>Upgrade to Premium - $9.99/month</CheckoutButton>
            </div>
            <p className="text-xs text-muted-foreground">
              Cancel anytime. No hidden fees.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Default alert variant
  return (
    <Alert className={className}>
      <div className="flex items-start gap-3">
        {message.icon}
        <div className="flex-1 space-y-3">
          <div>
            <AlertTitle>{message.title}</AlertTitle>
            <AlertDescription className="mt-1">
              {message.description}
            </AlertDescription>
          </div>
          <CheckoutButton size="sm">Upgrade Now</CheckoutButton>
        </div>
      </div>
    </Alert>
  );
};
