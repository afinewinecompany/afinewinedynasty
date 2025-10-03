import React from 'react';
import { HelpCircle } from 'lucide-react';
import { Tooltip } from '@/components/ui/Tooltip';

interface HelpIconProps {
  content: string | React.ReactNode;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export const HelpIcon: React.FC<HelpIconProps> = ({
  content,
  size = 'sm',
  className
}) => {
  const sizeClasses = {
    sm: 'h-4 w-4',
    md: 'h-5 w-5',
    lg: 'h-6 w-6'
  };

  return (
    <Tooltip content={content}>
      <span className={className}>
        <HelpCircle className={`${sizeClasses[size]} text-gray-400 hover:text-gray-600 cursor-help transition-colors`} />
      </span>
    </Tooltip>
  );
};

export default HelpIcon;