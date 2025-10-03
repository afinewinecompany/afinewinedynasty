/**
 * PaymentMethodCard component for managing payment methods.
 *
 * @module components/subscription/PaymentMethodCard
 */

import React, { useState } from 'react';
import { CreditCard, Edit2, Loader2 } from 'lucide-react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useToast } from '@/hooks/use-toast';
import { loadStripe } from '@stripe/stripe-js';
import {
  Elements,
  CardElement,
  useStripe,
  useElements,
} from '@stripe/react-stripe-js';

// Initialize Stripe (you'll need to add your publishable key)
const stripePromise = loadStripe(
  process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY || ''
);

interface PaymentMethodCardProps {
  currentPaymentMethod?: {
    card_brand: string;
    last4: string;
    exp_month: number;
    exp_year: number;
  };
  onUpdate?: () => void;
}

/**
 * Inner component that uses Stripe hooks
 */
const PaymentMethodForm: React.FC<{
  onSuccess: () => void;
  onCancel: () => void;
}> = ({ onSuccess, onCancel }) => {
  const stripe = useStripe();
  const elements = useElements();
  const [isProcessing, setIsProcessing] = useState(false);
  const { toast } = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!stripe || !elements) {
      return;
    }

    setIsProcessing(true);

    const cardElement = elements.getElement(CardElement);
    if (!cardElement) {
      setIsProcessing(false);
      return;
    }

    try {
      const { error, paymentMethod } = await stripe.createPaymentMethod({
        type: 'card',
        card: cardElement,
      });

      if (error) {
        toast({
          title: 'Error',
          description: error.message,
          variant: 'destructive',
        });
      } else if (paymentMethod) {
        // Here you would call your API to update the payment method
        // await updatePaymentMethod(paymentMethod.id);
        toast({
          title: 'Success',
          description: 'Payment method updated successfully',
        });
        onSuccess();
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to update payment method',
        variant: 'destructive',
      });
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="p-3 border rounded-md">
        <CardElement
          options={{
            style: {
              base: {
                fontSize: '16px',
                color: '#424770',
                '::placeholder': {
                  color: '#aab7c4',
                },
              },
            },
          }}
        />
      </div>
      <div className="flex gap-2">
        <Button type="submit" disabled={!stripe || isProcessing}>
          {isProcessing ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Processing...
            </>
          ) : (
            'Update Payment Method'
          )}
        </Button>
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </form>
  );
};

/**
 * Component for displaying and updating payment methods
 *
 * @param {PaymentMethodCardProps} props - Component props
 * @returns {JSX.Element} Rendered payment method card
 */
export const PaymentMethodCard: React.FC<PaymentMethodCardProps> = ({
  currentPaymentMethod,
  onUpdate,
}) => {
  const [isEditing, setIsEditing] = useState(false);

  const handleUpdateSuccess = () => {
    setIsEditing(false);
    if (onUpdate) {
      onUpdate();
    }
  };

  const getCardIcon = (brand: string) => {
    // You could add specific brand icons here
    return <CreditCard className="h-5 w-5" />;
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Payment Method</CardTitle>
            <CardDescription>Manage your payment information</CardDescription>
          </div>
          {!isEditing && currentPaymentMethod && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsEditing(true)}
            >
              <Edit2 className="h-4 w-4" />
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {isEditing ? (
          <Elements stripe={stripePromise}>
            <PaymentMethodForm
              onSuccess={handleUpdateSuccess}
              onCancel={() => setIsEditing(false)}
            />
          </Elements>
        ) : currentPaymentMethod ? (
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              {getCardIcon(currentPaymentMethod.card_brand)}
              <div>
                <p className="font-medium capitalize">
                  {currentPaymentMethod.card_brand} ••••{' '}
                  {currentPaymentMethod.last4}
                </p>
                <p className="text-sm text-muted-foreground">
                  Expires{' '}
                  {currentPaymentMethod.exp_month.toString().padStart(2, '0')}/
                  {currentPaymentMethod.exp_year}
                </p>
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              No payment method on file
            </p>
            <Button onClick={() => setIsEditing(true)}>
              Add Payment Method
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
};
