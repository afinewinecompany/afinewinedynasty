/**
 * CheckoutButton component for initiating Stripe checkout.
 *
 * @module components/subscription/CheckoutButton
 */

import React from 'react';
import { CreditCard, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useCheckout } from '@/hooks/useSubscription';
import { useToast } from '@/hooks/use-toast';

interface CheckoutButtonProps {
  planId?: string;
  variant?:
    | 'default'
    | 'outline'
    | 'secondary'
    | 'ghost'
    | 'link'
    | 'destructive';
  size?: 'default' | 'sm' | 'lg' | 'icon';
  className?: string;
  children?: React.ReactNode;
}

/**
 * Component for initiating Stripe checkout session
 *
 * @param {CheckoutButtonProps} props - Component props
 * @returns {JSX.Element} Rendered checkout button
 */
export const CheckoutButton: React.FC<CheckoutButtonProps> = ({
  planId = 'premium',
  variant = 'default',
  size = 'default',
  className = '',
  children,
}) => {
  const { initiateCheckout, isLoading, error } = useCheckout();
  const { toast } = useToast();

  const handleCheckout = async () => {
    try {
      initiateCheckout(planId);
    } catch (err) {
      toast({
        title: 'Checkout Error',
        description: 'Failed to start checkout process. Please try again.',
        variant: 'destructive',
      });
    }
  };

  React.useEffect(() => {
    if (error) {
      toast({
        title: 'Checkout Error',
        description: error.message || 'An error occurred during checkout',
        variant: 'destructive',
      });
    }
  }, [error, toast]);

  return (
    <Button
      onClick={handleCheckout}
      disabled={isLoading}
      variant={variant}
      size={size}
      className={className}
    >
      {isLoading ? (
        <>
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          Redirecting to checkout...
        </>
      ) : (
        <>
          <CreditCard className="mr-2 h-4 w-4" />
          {children || 'Subscribe Now'}
        </>
      )}
    </Button>
  );
};
