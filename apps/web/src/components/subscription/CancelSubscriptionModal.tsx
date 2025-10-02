/**
 * CancelSubscriptionModal component for subscription cancellation flow.
 *
 * @module components/subscription/CancelSubscriptionModal
 */

import React, { useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useSubscriptionManagement } from '@/hooks/useSubscription';
import { useToast } from '@/hooks/use-toast';

interface CancelSubscriptionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
  currentPeriodEnd?: string;
}

/**
 * Modal component for canceling subscription with confirmation
 *
 * @param {CancelSubscriptionModalProps} props - Component props
 * @returns {JSX.Element} Rendered cancellation modal
 */
export const CancelSubscriptionModal: React.FC<CancelSubscriptionModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  currentPeriodEnd
}) => {
  const [cancellationType, setCancellationType] = useState<'end_of_period' | 'immediate'>('end_of_period');
  const { cancelSubscription, isCanceling, cancelError } = useSubscriptionManagement();
  const { toast } = useToast();

  const handleCancel = async () => {
    const immediate = cancellationType === 'immediate';

    try {
      await cancelSubscription(immediate);

      toast({
        title: 'Subscription Canceled',
        description: immediate
          ? 'Your subscription has been canceled immediately.'
          : `Your subscription will remain active until ${currentPeriodEnd || 'the end of the billing period'}.`,
      });

      if (onSuccess) {
        onSuccess();
      }
      onClose();
    } catch (error) {
      toast({
        title: 'Cancellation Failed',
        description: 'Failed to cancel subscription. Please try again.',
        variant: 'destructive'
      });
    }
  };

  React.useEffect(() => {
    if (cancelError) {
      toast({
        title: 'Error',
        description: 'An error occurred while canceling your subscription.',
        variant: 'destructive'
      });
    }
  }, [cancelError, toast]);

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-destructive" />
            Cancel Subscription
          </DialogTitle>
          <DialogDescription>
            Are you sure you want to cancel your premium subscription? You'll lose access to premium features.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <Alert>
            <AlertDescription>
              <strong>You'll lose access to:</strong>
              <ul className="mt-2 ml-4 list-disc text-sm">
                <li>Full access to 500+ prospects</li>
                <li>Advanced filtering and search</li>
                <li>Prospect comparison tools</li>
                <li>Data export functionality</li>
                <li>ML-powered predictions</li>
              </ul>
            </AlertDescription>
          </Alert>

          <div className="space-y-3">
            <Label>When should we cancel?</Label>
            <RadioGroup
              value={cancellationType}
              onValueChange={(value) => setCancellationType(value as 'end_of_period' | 'immediate')}
            >
              <div className="flex items-start space-x-2">
                <RadioGroupItem value="end_of_period" id="end_of_period" />
                <div className="grid gap-1">
                  <Label htmlFor="end_of_period" className="font-normal cursor-pointer">
                    At the end of billing period
                  </Label>
                  <p className="text-sm text-muted-foreground">
                    Keep access until {currentPeriodEnd || 'your current billing period ends'}
                  </p>
                </div>
              </div>
              <div className="flex items-start space-x-2">
                <RadioGroupItem value="immediate" id="immediate" />
                <div className="grid gap-1">
                  <Label htmlFor="immediate" className="font-normal cursor-pointer">
                    Cancel immediately
                  </Label>
                  <p className="text-sm text-muted-foreground">
                    Lose access to premium features right away (no refund)
                  </p>
                </div>
              </div>
            </RadioGroup>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isCanceling}>
            Keep Subscription
          </Button>
          <Button
            variant="destructive"
            onClick={handleCancel}
            disabled={isCanceling}
          >
            {isCanceling ? 'Canceling...' : 'Cancel Subscription'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};