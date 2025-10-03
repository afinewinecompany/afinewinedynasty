/**
 * Premium feature types and interfaces
 */

export interface PremiumFeature {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  tier: 'free' | 'premium' | 'admin';
  category: 'data' | 'analysis' | 'export' | 'support' | 'beta';
  limit?: number;
}

export interface FeatureFlag {
  id: string;
  name: string;
  description: string;
  status: 'enabled' | 'disabled' | 'beta' | 'rollout' | 'deprecated';
  beta: boolean;
  rolloutPercentage?: number;
  tiers: string[];
}

export interface SubscriptionTier {
  id: 'free' | 'premium' | 'admin';
  name: string;
  price: number;
  currency: string;
  interval: 'month' | 'year';
  features: string[];
  limits: Record<string, number>;
}

export interface UpgradePromptConfig {
  title: string;
  description: string;
  features: string[];
  ctaText: string;
  ctaLink: string;
  showPricing: boolean;
}

export const PREMIUM_FEATURES: PremiumFeature[] = [
  {
    id: 'full-rankings',
    name: 'Full Top 500 Rankings',
    description: 'Access all 500 dynasty prospects instead of just top 100',
    enabled: true,
    tier: 'premium',
    category: 'data',
    limit: 500,
  },
  {
    id: 'advanced-filters',
    name: 'Advanced Filtering',
    description: 'Complex multi-criteria filtering with AND/OR operations',
    enabled: true,
    tier: 'premium',
    category: 'analysis',
  },
  {
    id: 'unlimited-comparisons',
    name: 'Unlimited Comparisons',
    description: 'Compare up to 10 prospects simultaneously',
    enabled: true,
    tier: 'premium',
    category: 'analysis',
    limit: 10,
  },
  {
    id: 'historical-data',
    name: 'Historical Data Access',
    description: 'View performance trends and season-over-season comparisons',
    enabled: true,
    tier: 'premium',
    category: 'data',
  },
  {
    id: 'enhanced-outlooks',
    name: 'Enhanced AI Outlooks',
    description: 'Personalized ML predictions with detailed explanations',
    enabled: true,
    tier: 'premium',
    category: 'analysis',
  },
  {
    id: 'data-export',
    name: 'Data Export',
    description: 'Export data in CSV, PDF, and JSON formats',
    enabled: true,
    tier: 'premium',
    category: 'export',
  },
  {
    id: 'priority-support',
    name: 'Priority Support',
    description: 'Faster response times and direct feature requests',
    enabled: true,
    tier: 'premium',
    category: 'support',
  },
  {
    id: 'saved-searches',
    name: 'Saved Searches',
    description: 'Save up to 50 custom search configurations',
    enabled: true,
    tier: 'premium',
    category: 'analysis',
    limit: 50,
  },
  {
    id: 'beta-features',
    name: 'Beta Feature Access',
    description: 'Early access to new features and functionality',
    enabled: true,
    tier: 'premium',
    category: 'beta',
  },
];

export const SUBSCRIPTION_TIERS: SubscriptionTier[] = [
  {
    id: 'free',
    name: 'Free',
    price: 0,
    currency: 'USD',
    interval: 'month',
    features: [
      'Top 100 prospects',
      'Basic filtering',
      'Compare 2 prospects',
      'Standard support',
      '5 saved searches',
    ],
    limits: {
      prospects: 100,
      comparisons: 2,
      savedSearches: 5,
      exports: 0,
    },
  },
  {
    id: 'premium',
    name: 'Premium',
    price: 9.99,
    currency: 'USD',
    interval: 'month',
    features: [
      'Full top 500 prospects',
      'Advanced filtering',
      'Compare up to 10 prospects',
      'Historical data access',
      'Enhanced AI outlooks',
      'Data export (CSV, PDF, JSON)',
      'Priority support',
      '50 saved searches',
      'Beta feature access',
    ],
    limits: {
      prospects: 500,
      comparisons: 10,
      savedSearches: 50,
      exports: 100,
    },
  },
];

export function getFeatureByTier(tier: 'free' | 'premium'): PremiumFeature[] {
  return PREMIUM_FEATURES.filter((feature) => {
    if (tier === 'premium') {
      return feature.tier === 'premium' || feature.tier === 'free';
    }
    return feature.tier === 'free';
  });
}

export function getTierLimits(
  tier: 'free' | 'premium'
): Record<string, number> {
  const tierConfig = SUBSCRIPTION_TIERS.find((t) => t.id === tier);
  return tierConfig?.limits || {};
}

export function getUpgradePrompt(feature: string): UpgradePromptConfig {
  const prompts: Record<string, UpgradePromptConfig> = {
    'full-rankings': {
      title: 'Unlock Full Rankings',
      description: 'Get access to all 500 dynasty prospects',
      features: [
        '400 additional prospects',
        'Deeper dynasty targets',
        'Complete player pool',
      ],
      ctaText: 'Upgrade to Premium',
      ctaLink: '/subscription',
      showPricing: true,
    },
    'advanced-filters': {
      title: 'Advanced Filtering',
      description: 'Find exactly the prospects you need',
      features: [
        'Complex criteria',
        'AND/OR operations',
        'Save custom filters',
      ],
      ctaText: 'Unlock Advanced Filters',
      ctaLink: '/subscription',
      showPricing: true,
    },
    'data-export': {
      title: 'Export Your Data',
      description: 'Download rankings and comparisons',
      features: ['CSV format', 'PDF reports', 'JSON data'],
      ctaText: 'Get Export Access',
      ctaLink: '/subscription',
      showPricing: true,
    },
    'historical-data': {
      title: 'Historical Trends',
      description: 'Track prospect performance over time',
      features: [
        'Performance trajectories',
        'Season comparisons',
        'Trend analysis',
      ],
      ctaText: 'View Historical Data',
      ctaLink: '/subscription',
      showPricing: true,
    },
    default: {
      title: 'Premium Feature',
      description: 'This feature requires a premium subscription',
      features: SUBSCRIPTION_TIERS[1].features,
      ctaText: 'Upgrade Now',
      ctaLink: '/subscription',
      showPricing: true,
    },
  };

  return prompts[feature] || prompts.default;
}
