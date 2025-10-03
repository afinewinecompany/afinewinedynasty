import React from 'react';
import { useAuth } from '@/hooks/useAuth';
import UpgradePrompt from '../subscription/UpgradePrompt';

interface ExclusiveContentProps {
  children: React.ReactNode;
  feature: string;
  requiresPremium?: boolean;
  fallback?: React.ReactNode;
  className?: string;
}

/**
 * Wrapper component for premium-only content with automatic gating
 *
 * @component ExclusiveContent
 * @param {ExclusiveContentProps} props - Component props
 * @returns {JSX.Element} Rendered content or upgrade prompt
 *
 * @example
 * ```tsx
 * <ExclusiveContent feature="advanced-filters">
 *   <AdvancedFilters />
 * </ExclusiveContent>
 * ```
 *
 * @since 1.0.0
 */
export const ExclusiveContent: React.FC<ExclusiveContentProps> = ({
  children,
  feature,
  requiresPremium = true,
  fallback,
  className
}) => {
  const { user } = useAuth();
  const isPremium = user?.subscriptionTier === 'premium';

  // If premium is not required, always show content
  if (!requiresPremium) {
    return <>{children}</>;
  }

  // If user is premium, show content
  if (isPremium) {
    return <div className={className}>{children}</div>;
  }

  // Show fallback or upgrade prompt
  return fallback ? (
    <>{fallback}</>
  ) : (
    <UpgradePrompt feature={feature} />
  );
};

export default ExclusiveContent;