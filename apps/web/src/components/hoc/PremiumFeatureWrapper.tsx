import React from 'react';
import { useFeatureAccess } from '@/hooks/useFeatureAccess';
import UpgradePrompt from '../subscription/UpgradePrompt';
import { Lock } from 'lucide-react';

interface PremiumFeatureWrapperProps {
  children: React.ReactNode;
  feature: keyof ReturnType<typeof useFeatureAccess>;
  fallback?: React.ReactNode;
  showLock?: boolean;
  className?: string;
}

/**
 * Higher-Order Component for wrapping premium features with access control
 *
 * @component PremiumFeatureWrapper
 * @param {PremiumFeatureWrapperProps} props - Component props
 * @returns {JSX.Element} Wrapped content or fallback
 *
 * @example
 * ```tsx
 * <PremiumFeatureWrapper feature="canExport">
 *   <ExportButton />
 * </PremiumFeatureWrapper>
 * ```
 *
 * @since 1.0.0
 */
export const PremiumFeatureWrapper: React.FC<PremiumFeatureWrapperProps> = ({
  children,
  feature,
  fallback,
  showLock = true,
  className,
}) => {
  const access = useFeatureAccess();

  // Check if user has access to the feature
  const hasAccess = access[feature];

  // If user has access, show the content
  if (hasAccess === true || (typeof hasAccess === 'number' && hasAccess > 0)) {
    return <div className={className}>{children}</div>;
  }

  // If custom fallback provided, use it
  if (fallback) {
    return <>{fallback}</>;
  }

  // Default fallback with lock icon or upgrade prompt
  if (showLock) {
    return (
      <div className={`relative ${className}`}>
        <div className="opacity-50 pointer-events-none">{children}</div>
        <div className="absolute inset-0 flex items-center justify-center bg-white/80 dark:bg-gray-900/80 rounded-lg">
          <div className="text-center">
            <Lock className="w-8 h-8 mx-auto mb-2 text-gray-500" />
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Premium Feature
            </p>
            <UpgradePrompt feature={String(feature)} compact />
          </div>
        </div>
      </div>
    );
  }

  // Simple upgrade prompt
  return <UpgradePrompt feature={String(feature)} />;
};

export default PremiumFeatureWrapper;
