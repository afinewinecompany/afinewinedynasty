import { useMemo } from 'react';
import { useAuth } from './useAuth';

export interface FeatureAccess {
  prospectsLimit: number;
  canExport: boolean;
  canUseAdvancedFilters: boolean;
  canCompare: boolean;
  canAccessHistorical: boolean;
  canAccessEnhancedOutlooks: boolean;
  hasPrioritySupport: boolean;
  canVoteOnFeatures: boolean;
  canCreateFeatureRequests: boolean;
  maxSavedSearches: number;
  maxComparisons: number;
  canAccessBetaFeatures: boolean;
}

/**
 * Custom hook for checking user feature access based on subscription tier
 *
 * @hook useFeatureAccess
 * @returns {FeatureAccess} Object containing feature access flags
 *
 * @example
 * ```tsx
 * const access = useFeatureAccess();
 * if (access.canExport) {
 *   // Show export button
 * }
 * ```
 *
 * @since 1.0.0
 */
export function useFeatureAccess(): FeatureAccess {
  const { user } = useAuth();

  return useMemo(() => {
    const isPremium = user?.subscriptionTier === 'premium';
    const isAdmin = user?.subscriptionTier === 'admin';
    const isPremiumOrAdmin = isPremium || isAdmin;

    return {
      // Prospect limits
      prospectsLimit: isPremiumOrAdmin ? 500 : 100,

      // Export capabilities
      canExport: isPremiumOrAdmin,

      // Advanced features
      canUseAdvancedFilters: isPremiumOrAdmin,
      canCompare: isPremiumOrAdmin,
      canAccessHistorical: isPremiumOrAdmin,
      canAccessEnhancedOutlooks: isPremiumOrAdmin,

      // Support features
      hasPrioritySupport: isPremiumOrAdmin,
      canVoteOnFeatures: isPremiumOrAdmin,
      canCreateFeatureRequests: isPremiumOrAdmin,

      // Limits
      maxSavedSearches: isPremiumOrAdmin ? 50 : 5,
      maxComparisons: isPremiumOrAdmin ? 10 : 2,

      // Beta access
      canAccessBetaFeatures: isPremiumOrAdmin
    };
  }, [user?.subscriptionTier]);
}

/**
 * Check if a specific feature requires premium access
 *
 * @function isPremiumFeature
 * @param {keyof FeatureAccess} feature - Feature to check
 * @returns {boolean} True if feature requires premium
 *
 * @example
 * ```tsx
 * if (isPremiumFeature('canExport')) {
 *   // Show premium badge
 * }
 * ```
 *
 * @since 1.0.0
 */
export function isPremiumFeature(feature: keyof FeatureAccess): boolean {
  const premiumFeatures: Set<keyof FeatureAccess> = new Set([
    'canExport',
    'canUseAdvancedFilters',
    'canCompare',
    'canAccessHistorical',
    'canAccessEnhancedOutlooks',
    'hasPrioritySupport',
    'canVoteOnFeatures',
    'canCreateFeatureRequests',
    'canAccessBetaFeatures'
  ]);

  return premiumFeatures.has(feature);
}

/**
 * Get feature limit for current user
 *
 * @function getFeatureLimit
 * @param {keyof FeatureAccess} feature - Feature to check
 * @param {boolean} isPremium - Whether user is premium
 * @returns {number|boolean} Feature limit or access boolean
 *
 * @since 1.0.0
 */
export function getFeatureLimit(
  feature: keyof FeatureAccess,
  isPremium: boolean
): number | boolean {
  const limits: Record<string, { free: number | boolean; premium: number | boolean }> = {
    prospectsLimit: { free: 100, premium: 500 },
    maxSavedSearches: { free: 5, premium: 50 },
    maxComparisons: { free: 2, premium: 10 },
    canExport: { free: false, premium: true },
    canUseAdvancedFilters: { free: false, premium: true },
    canCompare: { free: false, premium: true },
    canAccessHistorical: { free: false, premium: true },
    canAccessEnhancedOutlooks: { free: false, premium: true },
    hasPrioritySupport: { free: false, premium: true },
    canVoteOnFeatures: { free: false, premium: true },
    canCreateFeatureRequests: { free: false, premium: true },
    canAccessBetaFeatures: { free: false, premium: true }
  };

  const limit = limits[feature];
  return limit ? (isPremium ? limit.premium : limit.free) : false;
}