import React from 'react';
import { Star } from 'lucide-react';
import { cn } from '@/lib/utils';

interface PremiumBadgeProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  showText?: boolean;
}

/**
 * Premium badge component for visual identification of premium features/users
 *
 * @component PremiumBadge
 * @param {PremiumBadgeProps} props - Component props
 * @returns {JSX.Element} Rendered premium badge
 *
 * @example
 * ```tsx
 * <PremiumBadge size="md" showText={true} />
 * ```
 *
 * @since 1.0.0
 */
export const PremiumBadge: React.FC<PremiumBadgeProps> = ({
  size = 'md',
  className,
  showText = true
}) => {
  const sizeClasses = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-3 py-1 text-sm',
    lg: 'px-4 py-1.5 text-base'
  };

  const iconSizes = {
    sm: 'w-3 h-3',
    md: 'w-4 h-4',
    lg: 'w-5 h-5'
  };

  return (
    <div
      className={cn(
        'inline-flex items-center gap-1 rounded-full',
        'bg-gradient-to-r from-amber-500 to-amber-600',
        'text-white font-medium shadow-sm',
        'hover:from-amber-600 hover:to-amber-700 transition-colors',
        sizeClasses[size],
        className
      )}
    >
      <Star className={cn(iconSizes[size], 'fill-current')} />
      {showText && <span>Premium</span>}
    </div>
  );
};

export default PremiumBadge;