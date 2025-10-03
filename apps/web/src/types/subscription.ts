/**
 * Subscription type definitions for the A Fine Wine Dynasty platform.
 *
 * @module types/subscription
 */

export interface Subscription {
  id: number;
  user_id: number;
  stripe_subscription_id: string;
  stripe_customer_id: string;
  status:
    | 'active'
    | 'past_due'
    | 'unpaid'
    | 'canceled'
    | 'trialing'
    | 'incomplete';
  plan_id: 'free' | 'premium';
  current_period_start: string;
  current_period_end: string;
  cancel_at_period_end: boolean;
  canceled_at?: string;
  created_at: string;
  updated_at: string;
}

export interface PaymentMethod {
  id: number;
  stripe_payment_method_id: string;
  card_brand: string;
  last4: string;
  exp_month: number;
  exp_year: number;
  is_default: boolean;
  created_at: string;
}

export interface Invoice {
  id: number;
  stripe_invoice_id: string;
  amount_paid: number;
  status: 'paid' | 'open' | 'uncollectible' | 'void';
  billing_reason: string;
  invoice_pdf?: string;
  created_at: string;
}

export interface SubscriptionStatus {
  status: string;
  tier: 'free' | 'premium';
  plan_id?: string;
  current_period_start?: string;
  current_period_end?: string;
  cancel_at_period_end?: boolean;
  features: SubscriptionFeatures;
}

export interface SubscriptionFeatures {
  prospects_limit: number;
  export_enabled: boolean;
  advanced_filters_enabled: boolean;
  comparison_enabled: boolean;
}

export interface CheckoutSession {
  checkout_url: string;
  session_id: string;
  customer_id: string;
}

export interface PlanDetails {
  id: 'free' | 'premium';
  name: string;
  price: number;
  currency: string;
  interval: 'month' | 'year';
  features: string[];
  limitations?: string[];
  highlighted?: boolean;
}

export const SUBSCRIPTION_PLANS: PlanDetails[] = [
  {
    id: 'free',
    name: 'Free',
    price: 0,
    currency: 'USD',
    interval: 'month',
    features: [
      'Access to top 100 prospects',
      'Basic filtering options',
      'Dynasty rankings view',
      'Player profiles',
      'Basic statistical comparisons',
    ],
    limitations: [
      'No data export',
      'Limited to 100 prospects',
      'No advanced filters',
      'No comparison tools',
    ],
  },
  {
    id: 'premium',
    name: 'Premium',
    price: 9.99,
    currency: 'USD',
    interval: 'month',
    features: [
      'Full access to top 500 prospects',
      'Advanced filtering & search',
      'Unlimited prospect comparisons',
      'Data export (CSV/JSON)',
      'ML-powered predictions',
      'Historical analog matching',
      'Custom watchlists',
      'Priority support',
      'Early access to new features',
    ],
    highlighted: true,
  },
];
